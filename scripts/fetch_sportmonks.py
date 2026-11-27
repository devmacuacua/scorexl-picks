#!/usr/bin/env python3
"""Recolhe dados de futebol da Sportmonks (API v3) e grava data/football/AAAA-MM-DD.json
no MESMO formato que scripts/fetch_apisports.py gravava, para o scripts/football_model.py
continuar igual (substitui a API-Football, que terminou a 28/11/2026).

Uso: SPORTMONKS_TOKEN=... python scripts/fetch_sportmonks.py [--date AAAA-MM-DD] [--debug]
     --debug grava também data/football/raw/AAAA-MM-DD.json com as respostas brutas (para confirmar
     nomes de mercados/casas na primeira vez).

Campos que o modelo usa: fixtures[].{id, competition, kickoff_maputo, home, away, odds.bets,
team_form.home/away.last_games[].{league, goals_for, goals_against, stats_for.corners,
stats_against.corners}} e yesterday_results[].{id, home, away, goals_home, goals_away,
halftime, stats_home/away.corners, stats_1h_home/away.corners}.
Os nomes dos mercados nas odds são convertidos para os da api-sports ("Goals Over/Under",
"Both Teams Score", "Corners Over Under") com valores "Over 2.5"/"Under 2.5"/"Yes"/"No".

POR CONFIRMAR na primeira execução (não há acesso à API a partir daqui): ids das ligas, nomes
exatos dos mercados e se a 1xBet vem no plano. Ver "bookmakers_available" e "markets_seen".
Só biblioteca padrão. Erros de um pedido ficam em "errors" e não param o resto.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("SPORTMONKS_TOKEN", "").strip()
BASE = "https://api.sportmonks.com/v3/football"
MAPUTO = ZoneInfo("Africa/Maputo")

# ids Sportmonks (por confirmar; os nomes são os da api-sports, que é o que o modelo usa nas taxas base)
LEAGUES = {
    8: "Premier League",
    564: "La Liga",
    384: "Serie A",
    82: "Bundesliga",
    301: "Ligue 1",
    2: "Champions League",
    5: "Europa League",
    2286: "Conference League",
}
LAST_N = 5
FORM_DAYS = 60                       # janela para encontrar os últimos 5 jogos de cada equipa
BOOKMAKER_PREFERRED = ("1xbet", "bet365", "pinnacle", "unibet", "betfair")
FINISHED = {"FT", "AET", "FT_PEN", "PEN", "AP"}

# tipos de estatística Sportmonks -> chaves da api-sports
STAT_TYPES = {34: "corners", 86: "shots_on_target", 42: "shots", 84: "yellow_cards", 45: "possession"}

# mercados Sportmonks (nome em minúsculas, sem espaços extra) -> nome api-sports
MARKET_MAP = {
    "goals over/under": "Goals Over/Under",
    "over/under": "Goals Over/Under",
    "match goals": "Goals Over/Under",
    "alternative total goals": "Goals Over/Under",
    "both teams to score": "Both Teams Score",
    "corners over under": "Corners Over Under",
    "corners over/under": "Corners Over Under",
    "total corners": "Corners Over Under",
    "alternative corners": "Corners Over Under",
    "corners": "Corners Over Under",
    "fulltime result": "Match Winner",
    "full time result": "Match Winner",
    "match winner": "Match Winner",
}

ERRORS = []
CALLS = {"n": 0}
RAW = {}


def get(path, **params):
    """GET com tentativas e paginação; devolve a lista (ou o objeto) 'data'."""
    params = {k: v for k, v in params.items() if v is not None}
    params["api_token"] = TOKEN
    out, page = None, 1
    while True:
        params["page"] = page
        url = f"{BASE}/{path}?{urllib.parse.urlencode(params, safe=':,;')}"
        body = None
        for attempt in range(4):
            try:
                CALLS["n"] += 1
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(5 * (attempt + 1))
                    continue
                msg = e.read().decode("utf-8", "replace")[:300]
                ERRORS.append(f"{path} HTTP {e.code}: {msg}")
                return out if out is not None else []
            except Exception as e:  # noqa: BLE001
                time.sleep(3 * (attempt + 1))
                last = repr(e)
        if body is None:
            ERRORS.append(f"{path}: falhou após tentativas ({locals().get('last', '?')})")
            return out if out is not None else []
        data = body.get("data")
        if isinstance(data, list):
            out = (out or []) + data
        else:
            return data if data is not None else []
        RAW.setdefault(path, []).append({k: v for k, v in body.items() if k != "data"})
        pg = body.get("pagination") or {}
        if not pg.get("has_more"):
            return out
        page += 1


# ------------------------------------------------------------ conversões
def sides(f):
    """(home, away) participantes."""
    h = a = None
    for p in f.get("participants") or []:
        loc = ((p.get("meta") or {}).get("location") or "").lower()
        if loc == "home":
            h = p
        elif loc == "away":
            a = p
    return h, a


def state_short(f):
    st = f.get("state") or {}
    return (st.get("short_name") or st.get("developer_name") or st.get("state") or "").upper()


def score(f, description):
    """{'home': g, 'away': g} para CURRENT / 1ST_HALF / 2ND_HALF."""
    res = {}
    for s in f.get("scores") or []:
        if (s.get("description") or "").upper() != description:
            continue
        sc = s.get("score") or {}
        side = (sc.get("participant") or "").lower()
        if side in ("home", "away"):
            res[side] = sc.get("goals")
    return res if len(res) == 2 else None


def final_score(f):
    cur = score(f, "CURRENT")
    if cur:
        return cur
    h1, h2 = score(f, "1ST_HALF"), score(f, "2ND_HALF")
    if h1 and h2:
        return {k: h1[k] + h2[k] for k in ("home", "away")}
    return None


def stats_by_team(stat_list):
    out = {}
    for s in stat_list or []:
        k = STAT_TYPES.get(s.get("type_id"))
        if not k:
            continue
        v = (s.get("data") or {}).get("value")
        if isinstance(v, str):
            v = v.rstrip("%")
            try:
                v = float(v) if "." in v else int(v)
            except ValueError:
                continue
        out.setdefault(s.get("participant_id"), {})[k] = v if v is not None else 0
    return out


def first_half_stats(f):
    """Estatísticas da 1.ª parte via include periods.statistics (pode não existir no plano)."""
    for p in f.get("periods") or []:
        desc = (p.get("description") or p.get("type", {}).get("name") or "").lower()
        if p.get("sort_order") == 1 or "1st" in desc or "first" in desc:
            st = p.get("statistics")
            if st:
                return stats_by_team(st)
    return {}


def league_name(f):
    lg = f.get("league") or {}
    lid = f.get("league_id") or lg.get("id")
    return LEAGUES.get(lid) or lg.get("name") or ""


def kickoff_maputo(f):
    ts = f.get("starting_at_timestamp")
    if ts:
        t = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc)
    else:
        t = dt.datetime.fromisoformat((f.get("starting_at") or "1970-01-01 00:00:00").replace(" ", "T")).replace(tzinfo=dt.timezone.utc)
    return t.astimezone(MAPUTO)


def _num(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def build_odds(odds, seen_markets, seen_books):
    """Escolhe a casa preferida e converte para {"bookmaker", "bets": {nome api-sports: [{value, odd}]}}."""
    by_book = {}
    for o in odds or []:
        bk = o.get("bookmaker") or {}
        bname = (bk.get("name") or str(o.get("bookmaker_id"))).strip()
        seen_books.add(bname)
        by_book.setdefault(bname, []).append(o)
    if not by_book:
        return None
    chosen = None
    for pref in BOOKMAKER_PREFERRED:
        for b in by_book:
            if b.lower().replace(" ", "") == pref:
                chosen = b
                break
        if chosen:
            break
    chosen = chosen or next(iter(by_book))
    bets = {}
    for o in by_book[chosen]:
        mk = o.get("market") or {}
        mname = (mk.get("name") or o.get("market_description") or "").strip()
        seen_markets.add(mname)
        key = MARKET_MAP.get(" ".join(mname.lower().split()))
        if not key:
            continue
        label = (o.get("label") or o.get("name") or "").strip()
        odd = _num(o.get("value") or o.get("dp3"))
        if odd is None or odd <= 1:
            continue
        if o.get("stopped") or o.get("suspended"):
            continue
        ll = label.lower()
        if key == "Both Teams Score":
            v = "Yes" if ll in ("yes", "sim") else "No" if ll in ("no", "não") else None
        elif key == "Match Winner":
            v = {"1": "Home", "home": "Home", "x": "Draw", "draw": "Draw", "2": "Away", "away": "Away"}.get(ll)
        else:
            side = "Over" if ll.startswith("over") else "Under" if ll.startswith("under") else None
            line = _num(o.get("total")) or _num(o.get("handicap"))
            if line is None:                       # "Over 2.5" no próprio label/nome
                parts = label.split()
                line = _num(parts[-1]) if len(parts) > 1 else None
            v = f"{side} {line:g}" if side and line is not None else None
        if not v:
            continue
        lst = bets.setdefault(key, [])
        if not any(x["value"] == v for x in lst):     # 1.ª ocorrência (mercado principal antes do alternativo)
            lst.append({"value": v, "odd": f"{odd:.2f}"})
    return {"bookmaker": chosen, "bets": bets}


# ------------------------------------------------------------ recolha
FIX_INC = "participants;scores;state;league"


def fixtures_between(start, end, extra_inc="", filters=None, team=None):
    path = f"fixtures/between/{start}/{end}" + (f"/{team}" if team else "")
    inc = FIX_INC + (";" + extra_inc if extra_inc else "")
    return get(path, include=inc, filters=filters, per_page=50, timezone="UTC")


_forms = {}


def team_form(team_id, before):
    if team_id in _forms:
        return _forms[team_id]
    start = (before - dt.timedelta(days=FORM_DAYS)).isoformat()
    end = (before - dt.timedelta(days=1)).isoformat()
    fx = fixtures_between(start, end, "statistics", "fixtureStatisticTypes:34,42,86,84,45", team=team_id)
    fx = [f for f in fx if state_short(f) in FINISHED]
    fx.sort(key=lambda f: f.get("starting_at_timestamp") or 0, reverse=True)
    games, agg = [], {"for": {}, "against": {}}
    for f in fx[:LAST_N]:
        h, a = sides(f)
        if not h or not a:
            continue
        home = h["id"] == team_id
        opp = a if home else h
        sc = final_score(f) or {}
        st = stats_by_team(f.get("statistics"))
        mine, theirs = st.get(team_id, {}), st.get(opp["id"], {})
        gf, ga = sc.get("home" if home else "away"), sc.get("away" if home else "home")
        if gf is None or ga is None:
            continue
        games.append({"date": kickoff_maputo(f).date().isoformat(), "league": (f.get("league") or {}).get("name") or "",
                      "opponent": opp.get("name"), "venue": "home" if home else "away",
                      "goals_for": gf, "goals_against": ga, "stats_for": mine, "stats_against": theirs})
        for side, src in (("for", dict(mine, goals=gf)), ("against", dict(theirs, goals=ga))):
            for k, v in src.items():
                if isinstance(v, (int, float)) and k != "possession":
                    agg[side].setdefault(k, []).append(v)
    avg = {side: {k: round(sum(v) / len(v), 2) for k, v in m.items() if v} for side, m in agg.items()}
    _forms[team_id] = {"games_used": len(games), "avg": avg, "last_games": games}
    return _forms[team_id]


def football(d):
    leagues = ",".join(str(x) for x in LEAGUES)
    lf = f"fixtureLeagues:{leagues}"
    out = {"date": d.isoformat(), "sport": "football", "season": None,
           "note": "kickoff em hora de Maputo; team_form = últimos 5 jogos (todas as provas). Fonte Sportmonks v3.",
           "fixtures": [], "yesterday_results": []}
    # dia D e D-1 em hora de Maputo cobrem UTC de D-2 22h a D 22h
    span = fixtures_between((d - dt.timedelta(days=2)).isoformat(), (d + dt.timedelta(days=1)).isoformat(),
                            "statistics;periods.statistics", lf + ";fixtureStatisticTypes:34,42,86,84,45")
    prev = d - dt.timedelta(days=1)
    for f in span:
        if kickoff_maputo(f).date() != prev or state_short(f) not in FINISHED:
            continue
        h, a = sides(f)
        sc, ht = final_score(f), score(f, "1ST_HALF")
        if not h or not a or not sc:
            continue
        st, st1 = stats_by_team(f.get("statistics")), first_half_stats(f)
        out["yesterday_results"].append({
            "id": f["id"], "competition": league_name(f), "home": h["name"], "away": a["name"],
            "goals_home": sc["home"], "goals_away": sc["away"], "halftime": ht,
            "stats_home": st.get(h["id"], {}), "stats_away": st.get(a["id"], {}),
            "stats_1h_home": st1.get(h["id"]), "stats_1h_away": st1.get(a["id"]),
        })

    today = [f for f in span if kickoff_maputo(f).date() == d]
    seen_markets, seen_books = set(), set()
    for f in today:
        h, a = sides(f)
        if not h or not a:
            continue
        one = get(f"fixtures/{f['id']}", include="odds.bookmaker;odds.market")
        odds = one.get("odds") if isinstance(one, dict) else []
        out["fixtures"].append({
            "id": f["id"], "competition": league_name(f),
            "kickoff_maputo": kickoff_maputo(f).isoformat(timespec="seconds"),
            "status": state_short(f),
            "home": h["name"], "away": a["name"],
            "standings": None, "prediction": None,
            "odds": build_odds(odds, seen_markets, seen_books),
            "injuries": [],
            "team_form": {"home": team_form(h["id"], d), "away": team_form(a["id"], d)},
        })
    out["bookmakers_available"] = sorted(seen_books)
    out["markets_seen"] = sorted(seen_markets)
    if today and not any((x["odds"] or {}).get("bookmaker", "").lower() == "1xbet" for x in out["fixtures"]):
        ERRORS.append("1xBet não veio nas odds da Sportmonks (ver bookmakers_available); o modelo exige odd real da 1xBet")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="AAAA-MM-DD (por omissão: hoje em Maputo)")
    ap.add_argument("--debug", action="store_true", help="grava também as respostas brutas em data/football/raw/")
    args = ap.parse_args()
    if not TOKEN:
        sys.exit("SPORTMONKS_TOKEN em falta")
    d = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(MAPUTO).date()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "football")
    try:
        data = football(d)
    except Exception as e:  # noqa: BLE001
        data = {"date": d.isoformat(), "sport": "football", "fatal_error": repr(e)}
    data["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    data["source"] = "sportmonks.com"
    data["api_calls"] = CALLS["n"]
    data["errors"] = ERRORS[:50]
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, f"{d.isoformat()}.json")
    if not data.get("fixtures") and not data.get("yesterday_results") and os.path.exists(path):
        try:
            prev = json.load(open(path))
        except Exception:  # noqa: BLE001
            prev = {}
        if prev.get("fixtures") or prev.get("yesterday_results"):
            # recolha vazia/falhada não apaga um ficheiro bom; o erro fica num ficheiro à parte
            path = os.path.join(root, f"{d.isoformat()}.sportmonks_error.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    if args.debug:
        os.makedirs(os.path.join(root, "raw"), exist_ok=True)
        with open(os.path.join(root, "raw", f"{d.isoformat()}.json"), "w", encoding="utf-8") as fh:
            json.dump(RAW, fh, ensure_ascii=False, indent=1)
    print(f"football {d}: {len(data.get('fixtures', []))} jogos, {data['api_calls']} pedidos, {len(data['errors'])} erros -> {path}")


if __name__ == "__main__":
    main()
