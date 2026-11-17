#!/usr/bin/env python3
"""Liquida os palpites de uma liga de basquetebol (fora da NBA) com os resultados em data/<liga>/*.json.

Uso: python scripts/basket_settle.py <liga> [--today AAAA-MM-DD]
Para cada picks/<liga>/<dia>.json anterior a hoje e ainda fora de summary.days_processed:
  procura cada jogo (game_id, ou nomes casa/fora) em recent_results/yesterday_results de qualquer data/<liga>/*.json;
  grava results/<liga>/<dia>.json; se todos os palpites ficarem decididos, junta o dia a results/<liga>/summary.json.
Regras: handicap ganha se margem_lado + linha > 0 (= 0 → push); moneyline = vitória (inclui prolongamento);
total_over ganha se total > linha. Jogo adiado/cancelado → void (lucro 0, não conta como aposta).
Lucro: win = stake × (odds_ref − 1); loss = −stake; push/void = 0.
"""
import argparse
import datetime as dt
import glob
import json
import os
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FINAL = {"FT", "AOT"}
VOID = {"POST", "CANC", "ABD", "AWD", "INTR"}


def load_results(key):
    by_id, by_names = {}, {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", key, "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        for r in d.get("recent_results", []) + d.get("yesterday_results", []):
            if r.get("status") in FINAL | VOID:
                by_id[r["id"]] = r
                by_names[(r["home"], r["away"], r.get("date"))] = r
                by_names.setdefault((r["home"], r["away"], None), r)
    return by_id, by_names


def empty_summary(key, since):
    mk = lambda: {"bets": 0, "wins": 0, "profit_units": 0}  # noqa: E731
    return {"sport": key, "since": since, "updated": since, "bets": 0, "wins": 0, "losses": 0, "pushes": 0,
            "hit_rate": 0.0, "staked_units": 0, "profit_units": 0, "roi": 0.0,
            "by_confidence": {"alta": mk(), "media": mk()},
            "by_market": {"handicap": mk(), "moneyline": mk(), "total_over": mk()},
            "last_10": [], "days_processed": []}


def grade(p, r):
    if r["status"] in VOID:
        return "void", None, None
    sh, sa = r["score_home"], r["score_away"]
    margin_home = sh - sa
    total = sh + sa
    if p["market"] == "total_over":
        v = total - p["line"]
    else:
        side_margin = margin_home if p["side"] == "home" else -margin_home
        v = side_margin + (p.get("line") or 0)
    status = "win" if v > 0 else ("loss" if v < 0 else "push")
    return status, margin_home, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("league")
    ap.add_argument("--today", default=dt.datetime.now(ZoneInfo("Africa/Maputo")).date().isoformat())
    a = ap.parse_args()
    key = a.league
    by_id, by_names = load_results(key)
    spath = os.path.join(ROOT, "results", key, "summary.json")
    summary = json.load(open(spath)) if os.path.exists(spath) else None
    report = []

    for pf in sorted(glob.glob(os.path.join(ROOT, "picks", key, "*.json"))):
        day = os.path.basename(pf)[:-5]
        if day >= a.today:
            continue
        if summary and day in summary["days_processed"]:
            continue
        picks = json.load(open(pf)).get("picks", [])
        if summary is None:
            summary = empty_summary(key, day)
        rows, decided = [], True
        for p in picks:
            r = by_id.get(p.get("game_id"))
            if r is None:
                h, aw = p["match"].split(" vs ", 1)
                r = by_names.get((h, aw, day)) or by_names.get((h, aw, None))
            stake = p.get("stake_units", 0.5)
            odds = p.get("odds_ref") or p.get("min_odds")
            row = {"match": p["match"], "market": p["market"], "selection": p["selection"],
                   "stake_units": stake, "odds_ref": odds}
            if r is None:
                decided = False
                row.update(final_score=None, margin=None, total_points=None, status="pending", profit_units=0)
            else:
                status, margin, total = grade(p, r)
                profit = round(stake * (odds - 1), 3) if status == "win" else (-stake if status == "loss" else 0)
                row.update(final_score=f"{r['home']} {r['score_home']}-{r['score_away']} {r['away']}"
                           if status != "void" else f"{r['home']} vs {r['away']} ({r['status']})",
                           margin=margin, total_points=total, status=status, profit_units=profit)
            rows.append(row)
        counted = [x for x in rows if x["status"] in ("win", "loss", "push")]
        day_tot = {"bets": len(counted), "wins": sum(x["status"] == "win" for x in rows),
                   "losses": sum(x["status"] == "loss" for x in rows),
                   "pushes": sum(x["status"] == "push" for x in rows),
                   "profit_units": round(sum(x["profit_units"] for x in rows), 3)}
        os.makedirs(os.path.dirname(spath), exist_ok=True)
        json.dump({"date": day, "sport": key, "results": rows, "day": day_tot},
                  open(os.path.join(ROOT, "results", key, f"{day}.json"), "w"), ensure_ascii=False, indent=2)
        report.append({"date": day, "decided": decided, "day": day_tot, "results": rows})
        if not decided:
            continue
        s = summary
        for x, p in zip(rows, picks):
            if x["status"] not in ("win", "loss", "push"):
                continue
            s["bets"] += 1
            s["staked_units"] = round(s["staked_units"] + x["stake_units"], 3)
            s["profit_units"] = round(s["profit_units"] + x["profit_units"], 3)
            s["wins"] += x["status"] == "win"
            s["losses"] += x["status"] == "loss"
            s["pushes"] += x["status"] == "push"
            for grp, k in (("by_confidence", p.get("confidence", "media")), ("by_market", p["market"])):
                b = s[grp].setdefault(k, {"bets": 0, "wins": 0, "profit_units": 0})
                b["bets"] += 1
                b["wins"] += x["status"] == "win"
                b["profit_units"] = round(b["profit_units"] + x["profit_units"], 3)
            s["last_10"] = (s["last_10"] + [x["status"]])[-10:]
        s["days_processed"] = sorted(set(s["days_processed"]) | {day})
        decided_bets = s["wins"] + s["losses"]
        s["hit_rate"] = round(s["wins"] / decided_bets, 3) if decided_bets else 0.0
        s["roi"] = round(s["profit_units"] / s["staked_units"], 3) if s["staked_units"] else 0.0
        s["updated"] = a.today

    if summary is not None:
        os.makedirs(os.path.dirname(spath), exist_ok=True)
        json.dump(summary, open(spath, "w"), ensure_ascii=False, indent=2)
    print(json.dumps({"settled": report, "summary": summary}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
