#!/usr/bin/env python3
"""Recolhe dados da api-sports.io e grava-os em data/ para as tarefas de análise.

Uso: APISPORTS_KEY=... python scripts/fetch_apisports.py [--date AAAA-MM-DD] [--only nba|football]

Saídas:
  data/nba/AAAA-MM-DD.json       jogos NBA da data americana D (+ odds, classificação, resultados de D-1)
  data/football/AAAA-MM-DD.json  jogos de D (hora de Maputo) nas ligas seguidas (+ odds, lesões,
                                 médias de cantos/remates/golos dos últimos 5 jogos, resultados de D-1)
Só biblioteca padrão. Erros de um pedido ficam registados em "errors" e não param o resto.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

KEY = os.environ.get("APISPORTS_KEY", "").strip()
BASKET = "https://v1.basketball.api-sports.io"
FOOT = "https://v3.football.api-sports.io"
MAPUTO = ZoneInfo("Africa/Maputo")
NEW_YORK = ZoneInfo("America/New_York")

NBA_LEAGUE = 12
FOOTBALL_LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    2: "Champions League",
    3: "Europa League",
    848: "Conference League",
}
LAST_N = 5
BOOKMAKER_PREFERRED = ("1xBet", "Bet365", "Pinnacle", "Unibet", "Betfair")

ERRORS = []
CALLS = {"n": 0}
_cache = {}


def get(base, path, **params):
    """GET com tentativas; devolve a lista 'response' (todas as páginas)."""
    params = {k: v for k, v in params.items() if v is not None}
    key = (base, path, tuple(sorted(params.items())))
    if key in _cache:
        return _cache[key]
    out, page = [], params.get("page")
    while True:
        q = dict(params)
        if page:
            q["page"] = page
        url = f"{base}/{path}?{urllib.parse.urlencode(q)}"
        data = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
                with urllib.request.urlopen(req, timeout=30) as r:
                    CALLS["n"] += 1
                    data = json.load(r)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    ERRORS.append({"url": url.split("?")[0], "params": q, "error": str(e)})
                time.sleep(2 * (attempt + 1))
        if data is None:
            break
        errs = data.get("errors")
        if errs and (not isinstance(errs, list) or errs):
            ERRORS.append({"url": url.split("?")[0], "params": q, "error": errs})
            if isinstance(errs, dict) and any("rateLimit" in k or "requests" in k for k in errs):
                time.sleep(7)
        resp = data.get("response") or []
        out.extend(resp if isinstance(resp, list) else [resp])
        paging = data.get("paging") or {}
        if paging.get("current", 1) < paging.get("total", 1):
            page = paging["current"] + 1
            continue
        break
    _cache[key] = out
    return out


def season_football(d):
    return d.year if d.month >= 7 else d.year - 1


def season_nba(d):
    y = d.year if d.month >= 9 else d.year - 1
    return f"{y}-{y + 1}"


def pick_bookmaker(bookmakers):
    by_name = {b.get("name"): b for b in bookmakers or []}
    for name in BOOKMAKER_PREFERRED:
        if name in by_name:
            return by_name[name]
    return (bookmakers or [None])[0]


def slim_bets(bookmaker, wanted):
    if not bookmaker:
        return None
    bets = {}
    for b in bookmaker.get("bets", []):
        name = b.get("name", "")
        if any(w.lower() in name.lower() for w in wanted):
            bets[name] = [{"value": v.get("value"), "odd": v.get("odd")} for v in b.get("values", [])]
    return {"bookmaker": bookmaker.get("name"), "bets": bets}


# ----------------------------------------------------------------- NBA
def nba(d_us):
    season = season_nba(d_us)
    out = {"date": d_us.isoformat(), "sport": "NBA", "season": season,
           "note": "date = data americana; tipoff_maputo é a madrugada seguinte em Maputo",
           "games": [], "yesterday_results": [], "standings": []}

    games = get(BASKET, "games", league=NBA_LEAGUE, season=season, date=d_us.isoformat(),
                timezone="America/New_York")
    prev = get(BASKET, "games", league=NBA_LEAGUE, season=season,
               date=(d_us - dt.timedelta(days=1)).isoformat(), timezone="America/New_York")
    played_yesterday = set()
    for g in prev:
        h, a = g["teams"]["home"]["name"], g["teams"]["away"]["name"]
        played_yesterday.update([h, a])
        out["yesterday_results"].append({
            "id": g["id"], "home": h, "away": a,
            "status": g["status"]["short"],
            "score_home": g["scores"]["home"]["total"], "score_away": g["scores"]["away"]["total"],
        })

    for g in games:
        h, a = g["teams"]["home"]["name"], g["teams"]["away"]["name"]
        ts = dt.datetime.fromtimestamp(g["timestamp"], tz=dt.timezone.utc)
        odds_resp = get(BASKET, "odds", game=g["id"])
        books = odds_resp[0].get("bookmakers", []) if odds_resp else []
        out["games"].append({
            "id": g["id"], "home": h, "away": a,
            "tipoff_maputo": ts.astimezone(MAPUTO).isoformat(timespec="minutes"),
            "status": g["status"]["short"],
            "back_to_back": {"home": h in played_yesterday, "away": a in played_yesterday},
            "odds": slim_bets(pick_bookmaker(books), ["Home/Away", "Asian Handicap", "Over/Under", "3Way"]),
            "bookmakers_available": [b.get("name") for b in books],
        })

    for group in get(BASKET, "standings", league=NBA_LEAGUE, season=season):
        for t in group if isinstance(group, list) else [group]:
            out["standings"].append({
                "team": t["team"]["name"], "group": (t.get("group") or {}).get("name"),
                "position": t.get("position"),
                "won": t["games"]["win"]["total"], "lost": t["games"]["lose"]["total"],
                "points_for": t["points"]["for"], "points_against": t["points"]["against"],
                "form": t.get("form"),
            })
    return out


# ------------------------------------------------------------ FOOTBALL
STAT_KEYS = {"Corner Kicks": "corners", "Shots on Goal": "shots_on_target",
             "Total Shots": "shots", "Yellow Cards": "yellow_cards", "Ball Possession": "possession"}


def fixture_stats(fid):
    res = {}
    for team in get(FOOT, "fixtures/statistics", fixture=fid):
        vals = {}
        for s in team.get("statistics", []):
            k = STAT_KEYS.get(s.get("type"))
            if k:
                v = s.get("value")
                if isinstance(v, str) and v.endswith("%"):
                    v = int(v[:-1])
                vals[k] = v or 0
        res[team["team"]["id"]] = vals
    return res


def team_form(team_id, season):
    """Médias dos últimos LAST_N jogos terminados (todas as competições)."""
    fx = get(FOOT, "fixtures", team=team_id, last=LAST_N, status="FT-AET-PEN")
    games, agg = [], {"for": {}, "against": {}}
    for f in fx:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["id"] == team_id
        st = fixture_stats(fid)
        opp_id = f["teams"]["away" if home else "home"]["id"]
        mine, theirs = st.get(team_id, {}), st.get(opp_id, {})
        gf = f["goals"]["home" if home else "away"]
        ga = f["goals"]["away" if home else "home"]
        games.append({"date": f["fixture"]["date"][:10], "league": f["league"]["name"],
                      "opponent": f["teams"]["away" if home else "home"]["name"],
                      "venue": "home" if home else "away", "goals_for": gf, "goals_against": ga,
                      "stats_for": mine, "stats_against": theirs})
        for side, src in (("for", dict(mine, goals=gf)), ("against", dict(theirs, goals=ga))):
            for k, v in src.items():
                if isinstance(v, (int, float)) and k != "possession":
                    agg[side].setdefault(k, []).append(v)
    avg = {side: {k: round(sum(v) / len(v), 2) for k, v in m.items() if v} for side, m in agg.items()}
    return {"games_used": len(games), "avg": avg, "last_games": games}


def football(d):
    season = season_football(d)
    out = {"date": d.isoformat(), "sport": "football", "season": season,
           "note": "kickoff em hora de Maputo; team_form = médias dos últimos 5 jogos (todas as provas)",
           "fixtures": [], "yesterday_results": []}
    forms = {}
    prev_day = (d - dt.timedelta(days=1)).isoformat()

    for lid, lname in FOOTBALL_LEAGUES.items():
        for f in get(FOOT, "fixtures", league=lid, season=season, date=prev_day, timezone="Africa/Maputo"):
            if f["fixture"]["status"]["short"] not in ("FT", "AET", "PEN"):
                continue
            st = fixture_stats(f["fixture"]["id"])
            hid, aid = f["teams"]["home"]["id"], f["teams"]["away"]["id"]
            out["yesterday_results"].append({
                "id": f["fixture"]["id"], "competition": lname,
                "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"],
                "goals_home": f["goals"]["home"], "goals_away": f["goals"]["away"],
                "halftime": f["score"]["halftime"],
                "stats_home": st.get(hid, {}), "stats_away": st.get(aid, {}),
            })

        fixtures = get(FOOT, "fixtures", league=lid, season=season, date=d.isoformat(), timezone="Africa/Maputo")
        if not fixtures:
            continue
        odds_by_fixture = {o["fixture"]["id"]: o for o in
                           get(FOOT, "odds", league=lid, season=season, date=d.isoformat())}
        injuries = {}
        for inj in get(FOOT, "injuries", league=lid, season=season, date=d.isoformat()):
            injuries.setdefault(inj["fixture"]["id"], []).append({
                "team": inj["team"]["name"], "player": inj["player"]["name"],
                "type": inj["player"].get("type"), "reason": inj["player"].get("reason")})
        standings = {}
        for block in get(FOOT, "standings", league=lid, season=season):
            for group in block.get("league", {}).get("standings", []):
                for t in group:
                    standings[t["team"]["id"]] = {"rank": t["rank"], "points": t["points"],
                                                  "goals_diff": t["goalsDiff"], "played": t["all"]["played"],
                                                  "form": t.get("form")}
        for f in fixtures:
            fid = f["fixture"]["id"]
            hid, aid = f["teams"]["home"]["id"], f["teams"]["away"]["id"]
            for tid in (hid, aid):
                if tid not in forms:
                    forms[tid] = team_form(tid, season)
            pred = get(FOOT, "predictions", fixture=fid)
            pred = pred[0]["predictions"] if pred else None
            o = odds_by_fixture.get(fid)
            out["fixtures"].append({
                "id": fid, "competition": lname,
                "kickoff_maputo": f["fixture"]["date"],
                "status": f["fixture"]["status"]["short"],
                "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"],
                "standings": {"home": standings.get(hid), "away": standings.get(aid)},
                "prediction": pred and {"winner": (pred.get("winner") or {}).get("name"),
                                        "percent": pred.get("percent"), "advice": pred.get("advice"),
                                        "under_over": pred.get("under_over")},
                "odds": slim_bets(pick_bookmaker(o.get("bookmakers") if o else None),
                                  ["Match Winner", "Goals Over/Under", "Asian Handicap", "Corners Over Under",
                                   "Total Corners", "Shots on Target", "Both Teams Score"]),
                "injuries": injuries.get(fid, []),
                "team_form": {"home": forms[hid], "away": forms[aid]},
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="AAAA-MM-DD (por omissão: hoje em Maputo)")
    ap.add_argument("--only", choices=["nba", "football"])
    args = ap.parse_args()
    if not KEY:
        sys.exit("APISPORTS_KEY em falta")

    d = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(MAPUTO).date()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    jobs = []
    if args.only in (None, "football"):
        jobs.append(("football", d, football))
    if args.only in (None, "nba"):
        jobs.append(("nba", d, nba))  # jogos da data americana D = madrugada de D+1 em Maputo

    for sport, day, fn in jobs:
        ERRORS.clear()
        start = CALLS["n"]
        try:
            data = fn(day)
        except Exception as e:  # noqa: BLE001
            data = {"date": day.isoformat(), "sport": sport, "fatal_error": repr(e)}
        data["generated_at"] = generated
        data["source"] = "api-sports.io"
        data["api_calls"] = CALLS["n"] - start
        data["errors"] = ERRORS[:50]
        path = os.path.join(root, sport, f"{day.isoformat()}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        n = len(data.get("games", data.get("fixtures", [])))
        print(f"{sport} {day}: {n} jogos, {data['api_calls']} pedidos, {len(data['errors'])} erros -> {path}")


if __name__ == "__main__":
    main()
