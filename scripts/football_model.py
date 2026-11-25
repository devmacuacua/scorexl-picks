#!/usr/bin/env python3
"""Modelo de futebol (reset de 25/11/2026). Ver algos/football.md.

  build            → data/meta/football_model.json (taxas base por prova + calibração), a partir de data/study/
  picks D [--write] → avalia todos os mercados de data/football/D.json e escreve o rascunho em picks/football/D.json
  backtest         → testa a regra nos jogos com odds reais 1xBet em data/football/
"""
import glob, json, math, os, statistics as S, sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MODEL = os.path.join(ROOT, "data", "meta", "football_model.json")

# mercado → (chave 1xBet, linhas, variável do modelo, peso do modelo)
# peso do modelo: nos mercados de margem alta (1.ª/2.ª parte, cantos) o mercado é menos afinado → mais peso ao modelo;
# nos golos do jogo todo (margem ~4%, mercado afinado) o mercado manda.
MARKETS = {
    # "goals_1h": desativado a 25/11/2026 (decisão do Francisco: só jogo inteiro)
    # "corners_1h": desativado a 25/11/2026 (decisão do Francisco: só jogo inteiro)
    # "goals_2h": desativado a 25/11/2026 (decisão do Francisco: só jogo inteiro)
    "goals_ft": ("Goals Over/Under", [1.5, 2.5, 3.5], "g", 0.60),
    "corners_ft": ("Corners Over Under", [8.5, 9.5, 10.5, 11.5], "c", 0.60),
    "btts": ("Both Teams Score", [0.5], "g", 0.60),
    # "btts_1h": desativado a 25/11/2026 (decisão do Francisco: só jogo inteiro)
}
COMP_ALIAS = {"UEFA Champions League": "Champions League", "UEFA Europa League": "Europa League",
              "UEFA Europa Conference League": "Conference League", "UEFA Conference League": "Conference League"}
CUP_WORDS = ("cup", "copa", "pokal", "taça", "taca", "coupe", "coppa", "friendl", "trophy", "supercopa", "super cup")

# regra de decisão (algos/football.md)
MAX_DISAGREE = 0.10     # se o modelo e a 1xBet discordam mais do que isto (P Over), o modelo provavelmente não sabe algo → não entra
MIN_EV = 1.05           # P × odd mínimo
ODD_MIN, ODD_MAX = 1.40, 2.60
MAX_PICKS = 3
STAKE = 0.5
K_LEAGUE = 150          # encolhimento da taxa base da prova para a média geral (jogos)


def logit(p): return math.log(p / (1 - p))
def sigm(z): return 1 / (1 + math.exp(-z))


def outcome(r, mk):
    """Total do mercado num jogo do estudo (btts: 1 se ambas marcaram, linha 0.5)."""
    g, gh = r["goals"], r["goals_ht"]
    return {"goals_1h": sum(gh), "corners_1h": sum(r["corners_1h"]), "goals_2h": sum(g) - sum(gh),
            "goals_ft": sum(g), "corners_ft": sum(r["corners_ft"]),
            "btts": int(min(g) > 0), "btts_1h": int(min(gh) > 0)}[mk]


def load_study():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "study", "corners_1h_*.json"))):
        d = json.load(open(f))
        for fid, r in d["fixtures"].items():
            c1, cf, gh = r.get("corners_1h"), r.get("corners_ft"), r.get("goals_ht")
            if not c1 or None in c1 or not cf or None in cf or not gh or None in gh or not r.get("h2") or None in (r.get("goals") or [None]):
                continue
            h2 = sum(((x or {}).get("corners") or 0) for x in r["h2"])
            if sum(c1) + h2 != sum(cf) or sum(cf) == 0:
                continue
            rows.append(dict(r, fid=int(fid), season=d["season"]))
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def expected(hf, ha, af, aa):
    return (hf + aa) / 2 + (af + ha) / 2


def build():
    rows = load_study()
    hist = defaultdict(list)
    X = []  # (row, Ec, Eg)
    for r in rows:
        H, A = hist[(r["season"], r["home_id"])][-5:], hist[(r["season"], r["away_id"])][-5:]
        if len(H) >= 3 and len(A) >= 3:
            m = lambda T, i: S.mean(t[i] for t in T)
            X.append((r, expected(m(H, 0), m(H, 1), m(A, 0), m(A, 1)), expected(m(H, 2), m(H, 3), m(A, 2), m(A, 3))))
        for i, tid in ((0, r["home_id"]), (1, r["away_id"])):
            j = 1 - i
            hist[(r["season"], tid)].append((r["corners_ft"][i], r["corners_ft"][j], r["goals"][i], r["goals"][j]))
    model = {"built_from": f"{len(rows)} jogos limpos de data/study (calibração em {len(X)} com ≥3 jogos por equipa)",
             "mu": {"c": S.mean(x[1] for x in X), "g": S.mean(x[2] for x in X)}, "markets": {}}
    for mk, (_, lines, var, _w) in MARKETS.items():
        model["markets"][mk] = {}
        for L in lines:
            ys = [outcome(r, mk) > L for r in rows]
            overall = sum(ys) / len(ys)
            by = defaultdict(list)
            for r, y in zip(rows, ys):
                by[r["league"]].append(y)
            base = {lg: (sum(v) + K_LEAGUE * overall) / (len(v) + K_LEAGUE) for lg, v in by.items()}
            # inclinação comum: logit P = logit(base) + w·(E − mu), ajustada por descida de gradiente
            mu = model["mu"][var]
            data = [(logit(base[r["league"]]), (ec if var == "c" else eg) - mu, outcome(r, mk) > L) for r, ec, eg in X]
            w = 0.0
            for _ in range(400):
                g = sum((sigm(a + w * x) - y) * x for a, x, y in data) / len(data) + 0.5 * w / len(data)
                w -= 2.0 * g
            model["markets"][mk][str(L)] = {"overall": round(overall, 4), "w": round(w, 4),
                                            "base": {k: round(v, 4) for k, v in base.items()},
                                            "n": {k: len(v) for k, v in by.items()}}
    json.dump(model, open(MODEL, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({mk: {L: (v["overall"], v["w"]) for L, v in d.items()} for mk, d in model["markets"].items()}, indent=1))


def is_cup(name):
    n = (name or "").lower()
    return any(w in n for w in CUP_WORDS) and "champions" not in n and "europa" not in n and "conference" not in n


def team_avgs(tf):
    """Médias a favor/contra dos últimos jogos SEM taça/particulares. None se < 3 jogos com estatísticas."""
    g = [x for x in (tf or {}).get("last_games", []) if not is_cup(x.get("league"))]
    gc = [x for x in g if (x.get("stats_for") or {}).get("corners") is not None and (x.get("stats_against") or {}).get("corners") is not None]
    out = {"n_goals": len(g), "n_corners": len(gc)}
    if len(g) >= 3:
        out["gf"] = S.mean(x["goals_for"] for x in g); out["ga"] = S.mean(x["goals_against"] for x in g)
    if len(gc) >= 3:
        out["cf"] = S.mean(x["stats_for"]["corners"] for x in gc); out["ca"] = S.mean(x["stats_against"]["corners"] for x in gc)
    return out


def market_pairs(bets, key):
    if key.startswith("Both Teams Score"):
        v = {x["value"]: float(x["odd"]) for x in bets.get(key, [])}
        return {0.5: {"Over": v["Yes"], "Under": v["No"]}} if "Yes" in v and "No" in v else {}
    o = {}
    for v in bets.get(key, []):
        p = v["value"].split()
        if len(p) != 2:
            continue
        try:
            o.setdefault(float(p[1]), {})[p[0]] = float(v["odd"])
        except ValueError:
            pass
    return {l: v for l, v in o.items() if "Over" in v and "Under" in v}


def evaluate(fx, model):
    comp = COMP_ALIAS.get(fx["competition"], fx["competition"])
    tf = fx.get("team_form") or {}
    h, a = team_avgs(tf.get("home")), team_avgs(tf.get("away"))
    E = {}
    if "cf" in h and "cf" in a:
        E["c"] = expected(h["cf"], h["ca"], a["cf"], a["ca"])
    if "gf" in h and "gf" in a:
        E["g"] = expected(h["gf"], h["ga"], a["gf"], a["ga"])
    bets = (fx.get("odds") or {}).get("bets", {})
    cands = []
    for mk, (key, lines, var, w_model) in MARKETS.items():
        pairs = market_pairs(bets, key)
        for L in lines:
            m = model["markets"][mk][str(L)]
            base = m["base"].get(comp, m["overall"])
            x = E.get(var)
            p_model = sigm(logit(base) + m["w"] * ((x - model["mu"][var]) if x is not None else 0))
            od = pairs.get(L)
            if not od:
                continue
            io, iu = 1 / od["Over"], 1 / od["Under"]
            p_mkt = io / (io + iu)
            p_over = w_model * p_model + (1 - w_model) * p_mkt
            for side, p, odd in (("over", p_over, od["Over"]), ("under", 1 - p_over, od["Under"])):
                cands.append({"market": mk, "side": side, "line": L, "odd": odd, "p": p, "ev": p * odd,
                              "p_model_over": p_model, "p_mkt_over": p_mkt, "base_over": base, "E": x,
                              "data_ok": x is not None and abs(p_model - p_mkt) <= MAX_DISAGREE, "margin": io + iu - 1})
    return cands, E, h, a


LABEL = {"goals_1h": "golos na 1.ª parte", "corners_1h": "cantos na 1.ª parte", "goals_2h": "golos na 2.ª parte",
         "goals_ft": "golos no jogo", "corners_ft": "cantos no jogo", "btts": "ambas marcam", "btts_1h": "ambas marcam na 1.ª parte"}


def picks(d, write=False):
    model = json.load(open(MODEL))
    data = json.load(open(os.path.join(ROOT, "data", "football", f"{d}.json")))
    allc, avoid = [], []
    for fx in data["fixtures"]:
        if fx.get("status") not in (None, "NS", "TBD"):
            continue
        cands, E, h, a = evaluate(fx, model)
        ok = [c for c in cands if c["ev"] >= MIN_EV and ODD_MIN <= c["odd"] <= ODD_MAX and c["data_ok"]]
        match = f"{fx['home']} vs {fx['away']}"
        if ok:
            best = max(ok, key=lambda c: c["ev"])
            allc.append((best, fx, E))
        else:
            inr = [c for c in cands if ODD_MIN <= c["odd"] <= ODD_MAX]
            top = max((c for c in inr if c["data_ok"]), key=lambda c: c["ev"], default=None)
            dis = max((c for c in inr if not c["data_ok"] and c["E"] is not None and c["ev"] >= MIN_EV), key=lambda c: c["ev"], default=None)
            def lab(c):
                if c["market"].startswith("btts"):
                    return f"{LABEL[c['market']]} {'Sim' if c['side'] == 'over' else 'Não'}"
                return f"{'Mais' if c['side'] == 'over' else 'Menos'} de {c['line']} {LABEL[c['market']]}"
            parts = []
            if top:
                parts.append(f"Melhor opção: {lab(top)}, P {top['p']:.2f} × {top['odd']:.2f} = {top['ev']:.2f} (< {MIN_EV}).")
            if dis:
                parts.append(f"{lab(dis)} parecia ter valor ({dis['ev']:.2f}), mas o modelo ({dis['p_model_over']:.2f}) e a 1xBet ({dis['p_mkt_over']:.2f}) discordam mais de {MAX_DISAGREE} (P Over): o mercado deve saber algo que o modelo não sabe.")
            avoid.append({"match": match, "reason": " ".join(parts) or "Sem odds 1xBet utilizáveis."})
    allc.sort(key=lambda t: -t[0]["ev"])
    out = []
    for c, fx, E in allc[:MAX_PICKS]:
        if c["market"].startswith("btts"):
            sel = f"{LABEL[c['market']].capitalize()}: {'Sim' if c['side'] == 'over' else 'Não'}"
        else:
            sel = f"{'Mais' if c['side'] == 'over' else 'Menos'} de {c['line']} {LABEL[c['market']]}"
        out.append({
            "match": f"{fx['home']} vs {fx['away']}", "competition": fx["competition"], "kickoff_maputo": fx["kickoff_maputo"],
            "market": f"{c['market']}_{c['side']}", "ruleset": "v2",
            "selection": sel, "line": c["line"], "min_odds": round(1 / c["p"], 2), "odds_ref": c["odd"],
            "win_prob": round(c["p"], 3), "confidence": "media", "stake_units": STAKE,
            "reason": (f"P {c['p']:.2f} × {c['odd']:.2f} = {c['ev']:.2f}. Taxa base da prova (Over) {c['base_over']:.2f}, "
                       f"modelo (Over) {c['p_model_over']:.2f}, 1xBet sem margem (Over) {c['p_mkt_over']:.2f}; "
                       f"esperado do jogo ({'cantos' if 'corners' in c['market'] else 'golos'}, sem taças) {c['E']:.1f}.")})
    for c, fx, E in allc[MAX_PICKS:]:
        avoid.append({"match": f"{fx['home']} vs {fx['away']}", "reason": f"Cumpria a regra (EV {c['ev']:.2f}) mas ficou fora do limite de {MAX_PICKS} por dia."})
    res = {"date": d, "sport": "football", "note": "", "picks": out, "avoid": avoid}
    if write:
        p = os.path.join(ROOT, "picks", "football", f"{d}.json")
        json.dump(res, open(p, "w"), ensure_ascii=False, indent=2)
    return res


def outcome_y(mk, y, st, fid=None):
    """Total do mercado a partir de yesterday_results (e data/study para cantos da 1.ª parte). None se faltar."""
    if not y:
        return None
    ht = y.get("halftime") or {}
    ft = (y.get("goals_home"), y.get("goals_away"))
    if None in ft:
        return None
    hth = (ht.get("home"), ht.get("away")) if ht else (None, None)
    if mk == "corners_1h":
        return _halftime_corners(fid or y.get("id"), y, st)
    if mk == "corners_ft":
        a, b = (y.get("stats_home") or {}).get("corners"), (y.get("stats_away") or {}).get("corners")
        return None if a is None or b is None or (a == 0 and b == 0) else a + b
    if mk in ("goals_ft",):
        return sum(ft)
    if mk == "btts":
        return int(min(ft) > 0)
    if None in hth:
        return None
    return {"goals_1h": sum(hth), "goals_2h": sum(ft) - sum(hth), "btts_1h": int(min(hth) > 0)}.get(mk)


def backtest(per_market=False):
    model = json.load(open(MODEL))
    st = {}
    for f in glob.glob(os.path.join(ROOT, "data", "study", "*.json")):
        st.update(json.load(open(f))["fixtures"])
    res = {}
    files = sorted(glob.glob(os.path.join(ROOT, "data", "football", "*.json")))
    for f in files:
        for y in json.load(open(f)).get("yesterday_results", []):
            res[y["id"]] = y
    bets = []
    for f in files:
        for fx in json.load(open(f))["fixtures"]:
            y, s = res.get(fx["id"]), st.get(str(fx["id"]))
            cands, *_ = evaluate(fx, model)
            ok = [c for c in cands if c["ev"] >= MIN_EV and ODD_MIN <= c["odd"] <= ODD_MAX and c["data_ok"]]
            # per_market: a melhor opção de CADA mercado (para avaliar mercados); senão a melhor do jogo (regra real)
            groups = defaultdict(list)
            for c in ok:
                groups[c["market"] if per_market else "all"].append(c)
            for g in groups.values():
                c = max(g, key=lambda c: c["ev"])
                t = outcome_y(c["market"], y, st, fx["id"])
                if t is None:
                    continue
                win = (t > c["line"]) if c["side"] == "over" else (t < c["line"])
                bets.append((c["market"], c["side"], win, c["odd"]))
    agg = defaultdict(lambda: [0, 0, 0.0])
    for mk, sd, w, o in bets:
        for k in ("TOTAL", f"{mk}_{sd}"):
            agg[k][0] += 1; agg[k][1] += w; agg[k][2] += (o - 1) if w else -1
    for k, (n, w, p) in sorted(agg.items()):
        print(f"{k:18s} n={n:3d} acerto={w / n:.2f} ROI={p / n:+.3f}")


# ---------------------------------------------------------------- liquidação
def _halftime_corners(match_id, y, st):
    if y and y.get("stats_1h_home") and y.get("stats_1h_away"):
        a, b = y["stats_1h_home"].get("corners"), y["stats_1h_away"].get("corners")
        if a is not None and b is not None:
            return a + b
    s = st.get(str(match_id))
    if s and s.get("corners_1h") and None not in s["corners_1h"]:
        return sum(s["corners_1h"])
    return None


def _grade(total, line, side):
    """Devolve fração de lucro por unidade de odd: 'win', 'loss', 'push' (linhas inteiras) ou meio-resultados asiáticos."""
    frac = round(line % 1, 2)
    if frac in (0.25, 0.75):
        a, b = _grade(total, line - 0.25, side), _grade(total, line + 0.25, side)
        return (a, b)
    if total == line:
        return "push"
    win = total > line if side == "over" else total < line
    return "win" if win else "loss"


def settle(d):
    """Liquida picks/football/d.json com data/football/(d+1).json e data/study; revê pendentes antigos; reconstrói summary.json."""
    import datetime as dt
    nxt = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
    res = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "football", "*.json"))):
        try:
            for y in json.load(open(f)).get("yesterday_results", []):
                res[(y["home"], y["away"])] = y
        except Exception:
            pass
    st = {}
    for f in glob.glob(os.path.join(ROOT, "data", "study", "*.json")):
        st.update(json.load(open(f))["fixtures"])
    pdir, rdir = os.path.join(ROOT, "picks", "football"), os.path.join(ROOT, "results", "football")

    def grade_pick(p, y):
        mk = p["market"]
        side = "under" if mk.endswith("_under") else "over"
        base = mk.rsplit("_", 1)[0]
        if base not in MARKETS:
            return "legacy", None
        total = outcome_y(base, y, st)
        if total is None:
            return None, None
        return _grade(total, p["line"], side), total

    # 1) dia d (novo ficheiro) + 2) pendentes antigos
    targets = [d] + [os.path.basename(f)[:10] for f in sorted(glob.glob(os.path.join(rdir, "20*.json")))
                     if '"pending"' in open(f).read() and os.path.basename(f)[:10] != d]
    for day in targets:
        rpath = os.path.join(rdir, f"{day}.json")
        if os.path.exists(rpath):
            R = json.load(open(rpath))
        else:
            ppath = os.path.join(pdir, f"{day}.json")
            if not os.path.exists(ppath):
                continue
            P = json.load(open(ppath))
            R = {"date": day, "sport": "football", "results": []}
            for p in P.get("picks", []):
                R["results"].append({k: p.get(k) for k in ("match", "competition", "market", "selection", "line", "stake_units", "odds_ref", "confidence", "ruleset")}
                                    | {"status": "pending", "profit_units": 0, "odds_source": "real" if p.get("odds_ref") else "min_odds",
                                       "odds_used": p.get("odds_ref") or p.get("min_odds")})
        for r in R["results"]:
            if r["status"] != "pending":
                continue
            home, away = r["match"].split(" vs ")
            y = res.get((home, away))
            g, total = grade_pick(r, y)
            if g in (None, "legacy"):
                continue
            o = r.get("odds_used") or r.get("odds_ref")
            stake = r["stake_units"]
            parts = g if isinstance(g, tuple) else (g,)
            prof = 0.0
            for part in parts:
                prof += {"win": stake * (o - 1), "loss": -stake, "push": 0}[part] / len(parts)
            status = parts[0] if len(set(parts)) == 1 else ("half_win" if "win" in parts else "half_loss")
            r.update({"status": status, "profit_units": round(prof, 3), "final_stat": total,
                      "final_score": f"{y['goals_home']}-{y['goals_away']}",
                      "halftime_score": f"{y['halftime']['home']}-{y['halftime']['away']}"})
        rs = R["results"]
        R["day"] = {"bets": sum(r["status"] != "pending" for r in rs), "wins": sum(r["status"] in ("win", "half_win") for r in rs),
                    "losses": sum(r["status"] in ("loss", "half_loss") for r in rs), "pushes": sum(r["status"] == "push" for r in rs),
                    "pending": sum(r["status"] == "pending" for r in rs), "profit_units": round(sum(r["profit_units"] for r in rs), 3)}
        json.dump(R, open(rpath, "w"), ensure_ascii=False, indent=2)
    rebuild_summary()


def rebuild_summary():
    rdir = os.path.join(ROOT, "results", "football")
    days, allr = [], []
    for f in sorted(glob.glob(os.path.join(rdir, "20*.json"))):
        R = json.load(open(f)); days.append(R["date"])
        for r in R["results"]:
            allr.append(dict(r, date=R["date"]))

    def agg(rs):
        s = [r for r in rs if r["status"] != "pending"]
        st = sum(r["stake_units"] for r in s if r["status"] != "push")
        pr = round(sum(r["profit_units"] for r in s), 3)
        w = sum(r["status"] in ("win", "half_win") for r in s); l = sum(r["status"] in ("loss", "half_loss") for r in s)
        return {"bets": len(s), "wins": w, "losses": l, "pushes": sum(r["status"] == "push" for r in s),
                "pending": sum(r["status"] == "pending" for r in rs), "staked_units": round(st, 3), "profit_units": pr,
                "hit_rate": round(w / (w + l), 3) if w + l else None, "roi": round(pr / st, 3) if st else None}

    def group(key):
        g = defaultdict(list)
        for r in allr:
            g[key(r)].append(r)
        return {k: agg(v) for k, v in sorted(g.items())}

    T = agg(allr)
    out = {"sport": "football", "days_processed": days,
           "totals": {k: T[k] for k in ("bets", "wins", "losses", "pushes", "pending")},
           "hit_rate": T["hit_rate"], "staked_units": T["staked_units"], "profit_units": T["profit_units"], "roi": T["roi"],
           "by_ruleset": group(lambda r: r.get("ruleset") or "v1"),
           "by_confidence": group(lambda r: r.get("confidence") or "media"),
           "by_market": group(lambda r: r["market"]),
           "by_odds_source": group(lambda r: r.get("odds_source") or "min_odds"),
           "pending": [{"date": r["date"], "match": r["match"], "market": r["market"], "line": r.get("line")} for r in allr if r["status"] == "pending"],
           "last_10": [{"date": r["date"], "match": r["match"], "market": r["market"], "status": r["status"], "profit_units": r["profit_units"]}
                       for r in [x for x in allr if x["status"] != "pending"][-10:]],
           "nota": "v1 = regras até 25/11/2026 (Over 1.ª parte com Poisson, sobreconfiante); v2 = reset de 25/11 (algos/football.md). "
                   "O ROI justo é o de by_odds_source.real (min_odds subestima o lucro das vitórias)."}
    json.dump(out, open(os.path.join(rdir, "summary.json"), "w"), ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "picks":
        r = picks(sys.argv[2], "--write" in sys.argv)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif cmd == "backtest":
        backtest("--per-market" in sys.argv)
    elif cmd == "settle":
        settle(sys.argv[2])
