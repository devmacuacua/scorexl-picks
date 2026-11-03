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
