#!/usr/bin/env python3
"""Estudo: cantos na 1.ª parte (futebol). Recolhe da api-sports, para as ligas pedidas,
todos os jogos terminados da época com as estatísticas por parte (fixtures/statistics?half=true)
e grava data/study/corners_1h_<época>.json (incremental: jogos já gravados não voltam a ser pedidos).

Uso: APISPORTS_KEY=... python scripts/study_corners_1h.py [--season 2026] [--leagues 39,140,135,78,61] [--max-calls 900]
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_apisports as fa  # noqa: E402

DEFAULT_LEAGUES = "39,140,135,78,61,2,3,848"


def stat_list_to_dict(lst):
    out = {}
    for s in lst or []:
        k = fa.STAT_KEYS.get(s.get("type"))
        if k:
            v = s.get("value")
            if isinstance(v, str) and v.endswith("%"):
                v = int(v[:-1])
            out[k] = v or 0
    return out


def parse_half(team_item):
    """Devolve (full, h1, h2). Aceita os formatos conhecidos da api-sports com half=true."""
    full = stat_list_to_dict(team_item.get("statistics"))
    h1 = h2 = None
    for k, v in team_item.items():
        kl = k.lower()
        if not isinstance(v, list) or k == "statistics":
            continue
        if "1h" in kl or "first" in kl or kl.endswith("_1"):
            h1 = stat_list_to_dict(v)
        elif "2h" in kl or "second" in kl or kl.endswith("_2"):
            h2 = stat_list_to_dict(v)
    # formato alternativo: cada estatística com {"type", "value", "1h"/"first_half", ...}
    if h1 is None:
        alt1, alt2 = {}, {}
        for s in team_item.get("statistics") or []:
            k = fa.STAT_KEYS.get(s.get("type"))
            if not k:
                continue
            for hk, dst in (("1h", alt1), ("first_half", alt1), ("half1", alt1), ("2h", alt2), ("second_half", alt2), ("half2", alt2)):
                if hk in s:
                    dst[k] = s[hk] or 0
        if alt1:
            h1, h2 = alt1, alt2 or None
    return full, h1, h2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--leagues", default=DEFAULT_LEAGUES)
    ap.add_argument("--max-calls", type=int, default=900)
    args = ap.parse_args()
    if not fa.KEY:
        sys.exit("APISPORTS_KEY em falta")
    today = dt.datetime.now(fa.MAPUTO).date()
    season = args.season or fa.season_football(today)
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "study")
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, f"corners_1h_{season}.json")
    db = {"season": season, "fixtures": {}, "sample_raw": None}
    if os.path.exists(path):
        db = json.load(open(path))
    fx_db = db["fixtures"]
    start = fa.CALLS["n"]
    missing_half = 0
    for lid in [int(x) for x in args.leagues.split(",") if x.strip()]:
        lname = fa.FOOTBALL_LEAGUES.get(lid, str(lid))
        fixtures = fa.get(fa.FOOT, "fixtures", league=lid, season=season, status="FT-AET-PEN")
        print(f"{lname}: {len(fixtures)} jogos terminados")
        for f in sorted(fixtures, key=lambda x: x["fixture"]["timestamp"]):
            fid = str(f["fixture"]["id"])
            if fid in fx_db and fx_db[fid].get("corners_1h") is not None:
                continue
            if fa.CALLS["n"] - start >= args.max_calls:
                break
            resp = fa.get(fa.FOOT, "fixtures/statistics", fixture=int(fid), half="true")
            time.sleep(0.25)
            if db.get("sample_raw") is None and resp:
                db["sample_raw"] = resp
            hid, aid = f["teams"]["home"]["id"], f["teams"]["away"]["id"]
            by = {r["team"]["id"]: parse_half(r) for r in resp}
            fh, h1h, h2h = by.get(hid, ({}, None, None))
            fa_, h1a, h2a = by.get(aid, ({}, None, None))
            rec = {
                "league_id": lid, "league": lname, "round": f["league"].get("round"),
                "date": f["fixture"]["date"][:10], "timestamp": f["fixture"]["timestamp"],
                "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"],
                "home_id": hid, "away_id": aid,
                "goals": [f["goals"]["home"], f["goals"]["away"]],
                "goals_ht": [f["score"]["halftime"]["home"], f["score"]["halftime"]["away"]],
                "full": [fh, fa_],
                "h1": [h1h, h1a] if h1h is not None else None,
                "h2": [h2h, h2a] if h2h is not None else None,
                "corners_ft": [fh.get("corners"), fa_.get("corners")],
                "corners_1h": [h1h.get("corners"), h1a.get("corners")] if h1h and h1a else None,
            }
            if rec["corners_1h"] is None:
                missing_half += 1
            fx_db[fid] = rec
        if fa.CALLS["n"] - start >= args.max_calls:
            print("limite de pedidos atingido; volta a correr para continuar")
            break
    db["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    db["errors"] = fa.ERRORS[:30]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(db, fh, ensure_ascii=False, indent=0)
    n1 = sum(1 for r in fx_db.values() if r.get("corners_1h"))
    print(f"{fa.CALLS['n'] - start} pedidos; {len(fx_db)} jogos no ficheiro, {n1} com cantos da 1.ª parte; "
          f"{missing_half} sem dados por parte nesta corrida; {len(fa.ERRORS)} erros")


if __name__ == "__main__":
    main()
