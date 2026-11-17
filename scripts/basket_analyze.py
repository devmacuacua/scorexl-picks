#!/usr/bin/env python3
"""Analisa data/<liga>/<D>.json com os parâmetros de algos/params.json e propõe palpites.

Uso: python scripts/basket_analyze.py <liga> [--date AAAA-MM-DD] [--write]
  --write grava o rascunho em picks/<liga>/<D>.json (a tarefa revê lesões antes de publicar).

Modelo (ver algos/COMMON.md):
  margem esperada da casa M = w·M_mercado + (1−w)·M_modelo
    M_mercado = −(linha do Asian Handicap com odds Home/Away mais equilibradas)
    M_modelo  = s·(saldo/jogo casa − saldo/jogo fora) + hca,  s = n/(n+shrink_k)
  P(cobrir linha X do lado L) = Φ((M_L + X)/σ);  P(vitória) = Φ(M_L/σ)
  total esperado T = w·T_mercado + (1−w)·(média + s·(T_classificação − média)); P(Over N) = Φ((T−N)/(1.5σ))
Convenção api-sports: "Home N" = casa com handicap N; "Away N" = lado contrário (fora com −N).
Só biblioteca padrão.
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MAPUTO = ZoneInfo("Africa/Maputo")


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def phi_inv(p):
    lo, hi = -10.0, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_ah(values):
    """{N: {"home": odd, "away": odd}} com N = handicap da casa."""
    lines = {}
    for v in values or []:
        parts = (v.get("value") or "").split()
        if len(parts) != 2:
            continue
        side, n, odd = parts[0].lower(), fnum(parts[1]), fnum(v.get("odd"))
        if side in ("home", "away") and n is not None and odd:
            lines.setdefault(n, {})[side] = odd
    return lines


def parse_ou(values):
    lines = {}
    for v in values or []:
        parts = (v.get("value") or "").split()
        if len(parts) != 2:
            continue
        side, n, odd = parts[0].lower(), fnum(parts[1]), fnum(v.get("odd"))
        if side in ("over", "under") and n is not None and odd:
            lines.setdefault(n, {})[side] = odd
    return lines


def balanced(lines, a, b):
    best = None
    for n, o in lines.items():
        if a in o and b in o:
            gap = abs(o[a] - o[b])
            if best is None or gap < best[0]:
                best = (gap, n, o)
    return best


def standings_map(rows):
    """Primeira entrada por equipa (época regular / grupo principal)."""
    out = {}
    for r in rows:
        t = r.get("team")
        if not t or t in out:
            continue
        n = r.get("played") or ((r.get("won") or 0) + (r.get("lost") or 0))
        if not n:
            continue
        out[t] = {"n": n, "won": r.get("won"), "lost": r.get("lost"),
                  "pf": r["points_for"] / n, "pa": r["points_against"] / n,
                  "net": (r["points_for"] - r["points_against"]) / n}
    return out


def fmt_line(x):
    return f"{x:+g}"


def analyze(key, day, write=False):
    params = json.load(open(os.path.join(ROOT, "algos", "params.json")))
    c, p = params["common"], params[key]
    path = os.path.join(ROOT, "data", key, f"{day}.json")
    if not os.path.exists(path):
        sys.exit(f"falta {path}")
    data = json.load(open(path))
    st = standings_map(data.get("standings", []))
    sigma, hca, w = p["sigma"], p["hca"], p["w_market"]
    cands, avoid, games_out = [], [], []
    now = dt.datetime.now(MAPUTO)

    for g in data.get("games", []):
        h, a = g["home"], g["away"]
        match = f"{h} vs {a}"
        tip = dt.datetime.fromisoformat(g["tipoff_maputo"])
        if g.get("status") != "NS":
            avoid.append({"match": match, "reason": f"estado {g.get('status')}"})
            continue
        if tip <= now:
            avoid.append({"match": match, "reason": "já começou"})
            continue
        bets = (g.get("odds") or {}).get("bets") or {}
        book = (g.get("odds") or {}).get("bookmaker")
        ml = {x["value"].lower(): fnum(x["odd"]) for x in bets.get("Home/Away", []) if fnum(x.get("odd"))}
        if not ml.get("home") or not ml.get("away"):
            avoid.append({"match": match, "reason": "sem odds; a rever (entra se houver odds 1.80-2.00 com P×odd ≥ 1.03)"})
            continue
        ph = (1 / ml["home"]) / (1 / ml["home"] + 1 / ml["away"])
        ah = parse_ah(bets.get("Asian Handicap"))
        bal = balanced(ah, "home", "away")
        m_mkt = -bal[1] if bal else sigma * phi_inv(ph)
        sh, sa = st.get(h), st.get(a)
        if sh and sa:
            s = min(sh["n"], sa["n"]) / (min(sh["n"], sa["n"]) + p["shrink_k"])
            m_model = s * (sh["net"] - sa["net"]) + hca
            t_raw = (sh["pf"] + sa["pa"]) / 2 + (sa["pf"] + sh["pa"]) / 2
            t_model = p["avg_total"] + s * (t_raw - p["avg_total"])
        else:
            s, m_model, t_model = 0, m_mkt, None
        M = w * m_mkt + (1 - w) * m_model
        ou = parse_ou(bets.get("Over/Under"))
        obal = balanced(ou, "over", "under")
        t_mkt = obal[1] if obal else None
        T = (w * t_mkt + (1 - w) * t_model) if (t_mkt is not None and t_model is not None) else None
        b2b = g.get("back_to_back") or {}
        info = {"match": match, "tipoff_maputo": g["tipoff_maputo"], "p_home_market": round(ph, 3),
                "home_line_market": bal[1] if bal else None, "margin_market": round(m_mkt, 1),
                "margin_model": round(m_model, 1), "margin_blend": round(M, 1),
                "p_home_blend": round(phi(M / sigma), 3), "total_market": t_mkt,
                "total_model": round(t_model, 1) if t_model else None, "total_blend": round(T, 1) if T else None,
                "back_to_back": b2b, "shrink": round(s, 2)}
        games_out.append(info)

        fav = "home" if M >= 0 else "away"
        fav_team, dog_team = (h, a) if fav == "home" else (a, h)
        m_fav = abs(M)
        p_fav = phi(m_fav / sigma)
        base = {"match": match, "tipoff_maputo": tip.isoformat(timespec="seconds"),
                "game_id": g["id"], "bookmaker": book}
        game_c = []
        # handicap do favorito
        why = []
        if p_fav < p["fav_min"]:
            why.append(f"favorito {fav_team} {p_fav:.0%} < {p['fav_min']:.0%}")
        if b2b.get(fav):
            why.append(f"{fav_team} em back-to-back")
        if not why:
            maxl = p["max_line_home"] if fav == "home" else p["max_line_away"]
            for n, o in ah.items():
                line = n if fav == "home" else -n   # handicap do favorito
                odd = o.get(fav)
                if odd is None or line >= 0 or -line > maxl or not (c["min_odds"] <= odd <= c["max_odds"]):
                    continue
                pr = phi((m_fav + line) / sigma)
                ev = pr * odd
                if ev >= c["ev_min"]:
                    game_c.append(dict(base, market="handicap", selection=f"{fav_team} {fmt_line(line)}",
                                       side=fav, line=line, odds_ref=odd, win_prob=round(pr, 3), ev=round(ev, 3)))
        # azarão com pontos (ex.: GBL contra Olympiacos/Panathinaikos)
        if p.get("dog_points_min") and bal and abs(bal[1]) >= p["dog_points_min"]:
            dog = "away" if fav == "home" else "home"
            for n, o in ah.items():
                line = n if dog == "home" else -n
                odd = o.get(dog)
                if odd is None or line <= 0 or not (c["min_odds"] <= odd <= c["max_odds"]):
                    continue
                pr = phi((line - m_fav) / sigma)
                ev = pr * odd
                if ev >= c["ev_min"]:
                    game_c.append(dict(base, market="handicap", selection=f"{dog_team} {fmt_line(line)}",
                                       side=dog, line=line, odds_ref=odd, win_prob=round(pr, 3), ev=round(ev, 3)))
        # moneyline da equipa da casa (jogos equilibrados com vantagem do modelo)
        odd = ml["home"]
        if c["min_odds"] <= odd <= c["max_odds"] and not b2b.get("home"):
            pr = phi(M / sigma)
            ev = pr * odd
            if ev >= p["ml_ev_min"]:
                game_c.append(dict(base, market="moneyline", selection=f"{h} (vitória)", side="home", line=0,
                                   odds_ref=odd, win_prob=round(pr, 3), ev=round(ev, 3)))
        # Overs
        if p.get("overs") and T is not None and t_mkt is not None and T - t_mkt >= 0 and \
                (t_model - t_mkt) >= c["over_margin_min"]:
            for n, o in ou.items():
                odd = o.get("over")
                if odd is None or n % 1 == 0 or not (c["min_odds"] <= odd <= c["max_odds"]):
                    continue
                pr = phi((T - n) / (1.5 * sigma))
                ev = pr * odd
                if ev >= c["ev_min"]:
                    game_c.append(dict(base, market="total_over", selection=f"Over {n:g}", side="total", line=n,
                                       odds_ref=odd, win_prob=round(pr, 3), ev=round(ev, 3)))
        if game_c:
            best = max(game_c, key=lambda x: (x["ev"], x["win_prob"]))
            best["reason"] = (f"Mercado {fav_team} {abs(m_mkt):.1f} pts (P casa {ph:.0%}); modelo {m_model:+.1f} "
                              f"(casa); combinado {M:+.1f}, σ {sigma}. P {best['win_prob']:.0%} × {best['odds_ref']} = {best['ev']}.")
            if best["market"] == "total_over":
                best["reason"] = f"Total mercado {t_mkt}, modelo {t_model:.1f}, combinado {T:.1f}. P {best['win_prob']:.0%} × {best['odds_ref']} = {best['ev']}."
            cands.append(best)
        else:
            avoid.append({"match": match, "reason": "; ".join(why) or
                          f"sem linha 1.80-2.00 com P×odd ≥ {c['ev_min']} (mercado {fav_team} {abs(m_mkt):.1f}, combinado {m_fav:.1f})"})

    cands.sort(key=lambda x: -x["ev"])
    picks, n_main, n_over = [], 0, 0
    for x in cands:
        if x["market"] == "total_over":
            if n_over >= c["max_overs"]:
                avoid.append({"match": x["match"], "reason": f"reserva: {x['selection']} @{x['odds_ref']} (máx. Overs)"}); continue
            n_over += 1
        else:
            if n_main >= c["max_picks"]:
                avoid.append({"match": x["match"], "reason": f"reserva: {x['selection']} @{x['odds_ref']} (máx. palpites)"}); continue
            n_main += 1
        x.update(min_odds=max(c["min_odds"], round(1 / x["win_prob"] + 0.005, 2)),
                 confidence="media", stake_units=c["stake"])
        picks.append(x)

    out = {"date": day, "sport": p["name"], "league_key": key,
           "note": f"Rascunho automático (generated_at dos dados {data.get('generated_at')}). Falta rever lesões.",
           "picks": picks, "avoid": avoid}
    if write:
        dst = os.path.join(ROOT, "picks", key, f"{day}.json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        json.dump(out, open(dst, "w"), ensure_ascii=False, indent=2)
    return out, games_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("league")
    ap.add_argument("--date", default=dt.datetime.now(MAPUTO).date().isoformat())
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    out, games = analyze(a.league, a.date, a.write)
    print(json.dumps({"games": games, "draft": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
