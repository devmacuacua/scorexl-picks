#!/usr/bin/env python3
"""Análise do estudo de cantos na 1.ª parte. Lê data/study/corners_1h_*.json e data/football/*.json (odds 1xBet)
e escreve um relatório em JSON (stdout ou --out)."""
import argparse
import glob
import json
import math
import os
import re
import statistics as S
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def pois_cdf(k, lam):
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(k) + 1))


def p_over(line, lam, disp=1.0):
    """P(X > line). disp>1 → binomial negativa com var = disp*mean."""
    if disp <= 1.0001:
        return 1 - pois_cdf(math.floor(line), lam)
    r = lam / (disp - 1)
    p = r / (r + lam)
    cdf = 0.0
    for k in range(int(math.floor(line)) + 1):
        cdf += math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1) + r * math.log(p) + k * math.log(1 - p))
    return 1 - cdf


def settle(total, line):
    """Lucro unitário de Over com odd 1 (para linhas .25/.75 asiáticas devolve fração ganha/perdida)."""
    frac = round(line % 1, 2)
    if frac in (0.25, 0.75):
        a, b = line - 0.25, line + 0.25
        return (settle(total, a) + settle(total, b)) / 2
    if total > line:
        return 1
    if total == line:
        return 0
    return -1


def load(seasons):
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "study", "corners_1h_*.json"))):
        season = int(re.findall(r"(\d{4})", os.path.basename(f))[0])
        if seasons and season not in seasons:
            continue
        d = json.load(open(f))
        for fid, r in d["fixtures"].items():
            if not r.get("corners_1h") or None in r["corners_1h"] or not r.get("h2"):
                continue
            ft = sum(x or 0 for x in r["corners_ft"])
            h2 = sum(((x or {}).get("corners") or 0) for x in r["h2"])
            if ft == 0 or sum(r["corners_1h"]) + h2 != ft:  # dados incompletos/inconsistentes
                continue
            rows.append(dict(r, fid=int(fid), season=season))
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def add_pre_match(rows, min_games=4, last_n=8):
    """Médias pré-jogo (só jogos anteriores, mesma época, todas as provas do estudo)."""
    hist = defaultdict(list)  # (season, team_id) -> lista de dicts por jogo
    for r in rows:
        feats = {}
        for side, tid, opp in (("home", r["home_id"], 1), ("away", r["away_id"], 0)):
            h = hist[(r["season"], tid)][-last_n:]
            feats[side + "_n"] = len(h)
            if len(h) >= min_games:
                for k in ("c1_for", "c1_against", "cft_for", "cft_against", "sh1_for", "sh1_against", "xg_for", "xg_against", "gd"):
                    vals = [g[k] for g in h if g.get(k) is not None]
                    feats[f"{side}_{k}"] = S.mean(vals) if vals else None
                same = [g for g in h if g["venue"] == side]
                if len(same) >= 2:
                    feats[f"{side}_c1_for_venue"] = S.mean(g["c1_for"] for g in same)
                    feats[f"{side}_c1_against_venue"] = S.mean(g["c1_against"] for g in same)
        r["pre"] = feats
        # atualizar histórico
        for i, (tid, venue) in enumerate(((r["home_id"], "home"), (r["away_id"], "away"))):
            j = 1 - i
            h1, ft = r["h1"], r["full"]
            hist[(r["season"], tid)].append({
                "venue": venue,
                "c1_for": r["corners_1h"][i], "c1_against": r["corners_1h"][j],
                "cft_for": r["corners_ft"][i], "cft_against": r["corners_ft"][j],
                "sh1_for": (h1[i] or {}).get("shots"), "sh1_against": (h1[j] or {}).get("shots"),
                "xg_for": (ft[i] or {}).get("xg"), "xg_against": (ft[j] or {}).get("xg"),
                "gd": (r["goals"][i] or 0) - (r["goals"][j] or 0),
            })


def expected(pre, kind):
    g = pre.get
    if kind == "c1":
        keys = ("home_c1_for", "away_c1_against", "away_c1_for", "home_c1_against")
    elif kind == "c1_venue":
        keys = ("home_c1_for_venue", "away_c1_against_venue", "away_c1_for_venue", "home_c1_against_venue")
    elif kind == "cft":
        keys = ("home_cft_for", "away_cft_against", "away_cft_for", "home_cft_against")
    else:
        raise ValueError(kind)
    v = [g(k) for k in keys]
    if None in v:
        return None
    return (v[0] + v[1]) / 2 + (v[2] + v[3]) / 2


def odds_index():
    """Odds 1xBet de 'Total Corners (1st Half)' por (data, casa, fora) — último ficheiro antes do jogo."""
    idx = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "football", "*.json"))):
        d = json.load(open(f))
        for fx in d.get("fixtures", []):
            b = ((fx.get("odds") or {}).get("bets") or {})
            m = b.get("Total Corners (1st Half)")
            if not m:
                continue
            lines = {}
            for o in m:
                mm = re.match(r"(Over|Under) ([\d.]+)$", o["value"])
                if mm:
                    lines.setdefault(float(mm.group(2)), {})[mm.group(1)] = float(o["odd"])
            idx[fx["id"]] = {"home": fx["home"], "away": fx["away"], "kickoff": fx.get("kickoff_maputo"),
                             "lines": {k: v for k, v in lines.items() if len(v) == 2},
                             "bookmaker": (fx.get("odds") or {}).get("bookmaker"),
                             "ft_lines": b.get("Corners Over Under")}
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="")
    ap.add_argument("--out")
    args = ap.parse_args()
    seasons = [int(x) for x in args.seasons.split(",") if x]
    rows = load(seasons)
    add_pre_match(rows)
    rep = {"n_games": len(rows)}
    tot = [sum(r["corners_1h"]) for r in rows]
    ft = [sum(r["corners_ft"]) for r in rows if None not in r["corners_ft"]]
    rep["mean_1h"] = round(S.mean(tot), 2)
    rep["var_1h"] = round(S.pvariance(tot), 2)
    rep["mean_ft"] = round(S.mean(ft), 2)
    rep["share_1h"] = round(sum(tot) / sum(ft), 3)
    rep["dist_1h"] = {k: sum(1 for t in tot if t == k) for k in range(0, max(tot) + 1)}
    rep["over_rates"] = {f"O{l}": round(sum(t > l for t in tot) / len(tot), 3) for l in (2.5, 3.5, 4.5, 5.5, 6.5)}
    # por liga
    byl = defaultdict(list)
    for r in rows:
        byl[r["league"]].append(r)
    rep["by_league"] = {}
    for l, rs in sorted(byl.items(), key=lambda x: -len(x[1])):
        t = [sum(r["corners_1h"]) for r in rs]
        rep["by_league"][l] = {"n": len(rs), "mean_1h": round(S.mean(t), 2), "var": round(S.pvariance(t), 2),
                               "O3.5": round(sum(x > 3.5 for x in t) / len(t), 3), "O4.5": round(sum(x > 4.5 for x in t) / len(t), 3),
                               "O5.5": round(sum(x > 5.5 for x in t) / len(t), 3),
                               "home_share": round(sum(r["corners_1h"][0] for r in rs) / max(1, sum(t)), 3)}
    # preditores
    rep["predictors"] = {}
    for kind in ("c1", "c1_venue", "cft"):
        pairs = [(expected(r["pre"], kind), sum(r["corners_1h"])) for r in rows]
        pairs = [(e, t) for e, t in pairs if e is not None]
        if len(pairs) < 30:
            continue
        xs, ys = zip(*pairs)
        if kind == "cft":
            # converter cantos totais esperados em 1.ª parte com a quota média
            xs = [x * rep["share_1h"] for x in xs]
        corr = S.correlation(xs, ys)
        mae = S.mean(abs(x - y) for x, y in zip(xs, ys))
        mae_base = S.mean(abs(rep["mean_1h"] - y) for y in ys)
        # buckets
        bk = defaultdict(list)
        for x, y in zip(xs, ys):
            bk[min(7, max(3, round(x * 2) / 2))].append(y)
        rep["predictors"][kind] = {"n": len(xs), "corr": round(corr, 3), "mae": round(mae, 2), "mae_media_liga": round(mae_base, 2),
                                   "buckets": {str(k): {"n": len(v), "real": round(S.mean(v), 2), "O4.5": round(sum(y > 4.5 for y in v) / len(v), 3),
                                                        "O3.5": round(sum(y > 3.5 for y in v) / len(v), 3)}
                                               for k, v in sorted(bk.items())}}
    # combinação simples (média de c1 e cft·quota) + regressão à média da liga
    comb = []
    for r in rows:
        a, b = expected(r["pre"], "c1"), expected(r["pre"], "cft")
        if a is None or b is None:
            continue
        b *= rep["share_1h"]
        lg = rep["by_league"][r["league"]]["mean_1h"]
        e = 0.35 * a + 0.35 * b + 0.30 * lg
        r["exp_comb"] = e
        comb.append((e, sum(r["corners_1h"])))
    if comb:
        xs, ys = zip(*comb)
        rep["predictors"]["combinado"] = {"n": len(xs), "corr": round(S.correlation(xs, ys), 3),
                                          "mae": round(S.mean(abs(x - y) for x, y in zip(xs, ys)), 2)}
        # calibração do modelo NB com o combinado
        disp = rep["var_1h"] / rep["mean_1h"]
        cal = defaultdict(lambda: [0, 0.0, 0])
        for e, t in comb:
            p = p_over(4.5, e, disp)
            b = round(p * 10) / 10
            cal[b][0] += 1
            cal[b][1] += p
            cal[b][2] += t > 4.5
        rep["calibration_O4.5"] = {str(k): {"n": v[0], "p_modelo": round(v[1] / v[0], 3), "real": round(v[2] / v[0], 3)}
                                   for k, v in sorted(cal.items())}
        rep["dispersion"] = round(disp, 3)
    # efeito favorito (diferença de golos pré-jogo)
    fav = defaultdict(list)
    for r in rows:
        p = r["pre"]
        if p.get("home_gd") is None or p.get("away_gd") is None:
            continue
        d = p["home_gd"] - p["away_gd"]
        k = "casa muito melhor (≥+1.5)" if d >= 1.5 else "casa melhor (+0.5..1.5)" if d >= 0.5 else "equilibrado" if d > -0.5 else "fora melhor (−0.5..−1.5)" if d > -1.5 else "fora muito melhor (≤−1.5)"
        fav[k].append(r)
    rep["by_favourite"] = {k: {"n": len(v), "mean_1h": round(S.mean(sum(r["corners_1h"]) for r in v), 2),
                               "O4.5": round(sum(sum(r["corners_1h"]) > 4.5 for r in v) / len(v), 3),
                               "home_share": round(sum(r["corners_1h"][0] for r in v) / max(1, sum(sum(r["corners_1h"]) for r in v)), 3)}
                           for k, v in fav.items()}
    # odds reais 1xBet (jogos com odds guardadas e resultado no estudo)
    oi = odds_index()
    bets = []
    for r in rows:
        o = oi.get(r["fid"])
        if not o:
            continue
        t = sum(r["corners_1h"])
        fair = None
        for L, v in o["lines"].items():
            dd = abs(v["Over"] - v["Under"])
            if fair is None or dd < fair[0]:
                fair = (dd, L)
        bets.append({"match": f"{r['home']} vs {r['away']}", "league": r["league"], "date": r["date"], "total_1h": t,
                     "fair_line": fair[1] if fair else None, "lines": o["lines"], "exp": r.get("exp_comb")})
    rep["with_1xbet_odds"] = len(bets)
    # estratégias com odds reais
    strat = {}
    for name, cond in {
        "Over linha justa (sempre)": lambda b: ("Over", b["fair_line"]),
        "Under linha justa (sempre)": lambda b: ("Under", b["fair_line"]),
        "Over 4.5 (sempre)": lambda b: ("Over", 4.5),
        "Under 4.5 (sempre)": lambda b: ("Under", 4.5),
        "Over 3.5 (sempre)": lambda b: ("Over", 3.5),
        "Over linha justa se exp ≥ linha+0.75": lambda b: ("Over", b["fair_line"]) if b["exp"] and b["fair_line"] and b["exp"] >= b["fair_line"] + 0.75 else None,
        "Under linha justa se exp ≤ linha−0.75": lambda b: ("Under", b["fair_line"]) if b["exp"] and b["fair_line"] and b["exp"] <= b["fair_line"] - 0.75 else None,
    }.items():
        n = pl = w = 0
        for b in bets:
            c = cond(b)
            if not c or c[1] is None or c[1] not in b["lines"]:
                continue
            side, L = c
            odd = b["lines"][L][side]
            res = settle(b["total_1h"], L)
            if side == "Under":
                res = -res if round(L % 1, 2) not in (0.25, 0.75) else -res
            n += 1
            gain = res * (odd - 1) if res > 0 else res
            pl += gain
            w += res > 0
        strat[name] = {"n": n, "wins": w, "profit_u": round(pl, 2), "roi": round(pl / n, 3) if n else None}
    rep["strategies_1xbet"] = strat
    # odds típicas 1xBet
    ex = defaultdict(list)
    for o in oi.values():
        for L, v in o["lines"].items():
            ex[L].append((v["Over"], v["Under"]))
    rep["odds_tipicas_1xbet"] = {str(L): {"n": len(v), "over_med": round(S.median(x for x, _ in v), 2), "under_med": round(S.median(y for _, y in v), 2),
                                          "margem": round(S.median(1 / x + 1 / y for x, y in v) - 1, 3)} for L, v in sorted(ex.items()) if len(v) >= 3}
    out = json.dumps(rep, ensure_ascii=False, indent=1)
    if args.out:
        open(args.out, "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
