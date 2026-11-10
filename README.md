# scorexl-picks

Feed diário de palpites gerado automaticamente para o ScoreXL.

- **Desporto:** NBA (início)
- **Atualização:** todos os dias às 21h39 (Africa/Maputo)
- **Ficheiros:** `picks/nba/AAAA-MM-DD.json`

## Formato

```json
{
  "date": "AAAA-MM-DD",
  "sport": "NBA",
  "picks": [
    {
      "match": "Knicks vs Bulls",
      "tipoff_maputo": "2026-11-05T02:30+02:00",
      "market": "handicap",
      "selection": "Knicks -6.5",
      "min_odds": 1.45,
      "win_prob": 0.82,
      "confidence": "alta",
      "stake_units": 1,
      "reason": "NYK 82%, CHI 1-6 e a jogar em dias seguidos"
    }
  ],
  "avoid": [
    { "match": "Rockets vs Celtics", "reason": "Boston em back-to-back" }
  ]
}
```

Campos: `market` = `handicap` | `moneyline`; `confidence` = `alta` | `media`; `stake_units` = unidades (1 unidade = 3% da banca).

Leitura raw: `https://raw.githubusercontent.com/devmacuacua/scorexl-picks/main/picks/nba/AAAA-MM-DD.json`

## Resultados (liquidação automática)

Todos os dias, a mesma tarefa liquida os palpites do dia anterior.

- `results/nba/AAAA-MM-DD.json` — resultado de cada palpite do dia
- `results/nba/summary.json` — acumulado desde o início (ROI, acerto, últimos 10)

```json
{
  "date": "AAAA-MM-DD",
  "sport": "NBA",
  "results": [
    {
      "match": "Knicks vs Bulls",
      "selection": "Knicks -6.5",
      "final_score": "NYK 112-101 CHI",
      "margin": 11,
      "status": "win",
      "stake_units": 1,
      "odds_ref": 1.45,
      "profit_units": 0.45
    }
  ],
  "day": { "bets": 1, "wins": 1, "losses": 0, "pushes": 0, "profit_units": 0.45 }
}
```

`summary.json`:

```json
{
  "sport": "NBA", "since": "AAAA-MM-DD", "updated": "AAAA-MM-DD",
  "bets": 0, "wins": 0, "losses": 0, "pushes": 0, "hit_rate": 0.0,
  "staked_units": 0, "profit_units": 0, "roi": 0.0,
  "by_confidence": { "alta": { "bets": 0, "wins": 0, "profit_units": 0 },
                     "media": { "bets": 0, "wins": 0, "profit_units": 0 } },
  "last_10": ["win", "loss"],
  "days_processed": ["AAAA-MM-DD"]
}
```

`status` = `win` | `loss` | `push` | `pending`. Lucro calculado em unidades com `odds_ref` = cota mínima recomendada (a cota real na casa pode ser maior).

## Futebol

- `picks/football/AAAA-MM-DD.json` — mesmo formato base, com campos extra:
  - `competition` (ex.: "UEFA Europa League"), `kickoff_maputo` (ISO 8601 com offset)
  - `market` = `moneyline` | `handicap` | `goals_over` | `corners_over` | `shots_on_target_over`
  - `line` (linha do mercado, ou `null` no moneyline), `test: true` nas entradas de teste (mercados 20%)
  - `win_prob` pode faltar quando não há probabilidade de modelo
- Mercados sempre no **total do jogo** (não por equipa).

## Dados brutos (api-sports.io)

A GitHub Action `.github/workflows/apisports.yml` recolhe dados da api-sports.io e grava-os em `data/`:

- `data/football/AAAA-MM-DD.json`: jogos do dia (hora de Maputo) nas 5 grandes ligas, Champions, Liga Europa e Conferência, com classificação, previsão, odds (1xBet quando disponível), lesões, médias dos últimos 5 jogos de cada equipa (cantos, remates enquadrados, golos, a favor e contra) e resultados com estatísticas de D-1.
- `data/nba/AAAA-MM-DD.json`: jogos da data americana D (madrugada de D+1 em Maputo), odds, back-to-back, classificação e resultados de D-1.

Horários: 07h45 (futebol + NBA) e 21h00 (NBA com odds atualizadas), hora de Maputo. Também corre à mão em Actions → "Dados api-sports" → Run workflow.

Requer o secret `APISPORTS_KEY` (Settings → Secrets and variables → Actions). As tarefas de análise usam estes ficheiros como fonte principal.
