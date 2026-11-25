# Estudo do reset (25/11/2026)

Dados: `data/study` (2 609 jogos limpos das 5 ligas + UCL/UEL/UECL, 2025/26 e 2026/27, com estatísticas por parte), e `data/football` 10–25/11 (66 jogos com odds 1xBet; 57 com resultado ao intervalo; 29 com cantos da 1.ª parte).

## 1. Previsibilidade (walk-forward, 2 114 jogos com ≥ 3 jogos por equipa)
| Variável | Média real | Correlação: média da liga | Correlação: método v1 (últimos 5) |
|---|---|---|---|
| Cantos 1.ª parte | 4.46 (var 5.14) | 0.05 | 0.10 |
| Golos 1.ª parte | 1.23 (var 1.21) | 0.07 | 0.09 (xG 0.10) |

Log-loss em 2026 (ajuste em 2025): o modelo calibrado melhora 0.5 a 1% sobre a taxa base. O sinal é real, mas pequeno.

## 2. Calibração do método v1
| v1 previa cantos 1.ª parte | Jogos | Média real | O3.5 | O4.5 | O5.5 |
|---|---|---|---|---|---|
| 4.0–4.5 | 746 | 4.34 | .62 | .45 | .27 |
| 4.5–5.0 | 609 | 4.65 | .65 | .48 | .33 |
| 5.0–5.5 | 248 | 4.75 | .70 | .52 | .34 |
| 5.5–6.0 | 36 | 5.22 | .78 | .61 | .42 |

| v1 previa golos 1.ª parte | Jogos | Média real | O0.5 | O1.5 |
|---|---|---|---|---|
| 1.4–1.6 | 352 | 1.32 | .72 | .39 |
| 1.6–1.8 | 154 | 1.32 | .71 | .42 |
| 1.8–2.0 | 75 | 1.65 | .84 | .44 |
| 2.0–2.3 | 23 | 1.43 | .78 | .39 |

Conclusão: a v1 dava 0.62–0.83 onde a realidade foi 0.40–0.60. Daí as apostas sem valor.

## 3. 1xBet: implícita sem margem vs real (57 jogos)
| Mercado | Margem | Implícita (Over) | Real | ROI Over | ROI Under |
|---|---|---|---|---|---|
| Golos 1.ª parte O0.5 | 6.5% | .749 | .719 | −9% | +9% |
| Golos 1.ª parte O1.5 | 5.5% | .424 | .351 | −19% | +8% |
| Cantos 1.ª parte O4.5 (29) | 8.0% | .506 | .621 | +14% | −29% |
| Golos jogo O2.5 | 3.6% | .602 | .474 | −25% | +30% |
| Cantos jogo O9.5 | 8.8% | .519 | .526 | −7% | −10% |

As amostras são pequenas e não provam nada. Mas o padrão (Over caro nos golos) bate com o histórico: O1.5 na 1.ª parte foi 0.357 em 2 609 jogos.

## 4. Backtest da regra v2 nos jogos com odds reais
25 apostas: 64% de acerto, ROI +18% (22 Under 1.5 golos 1.ª parte). **Não é prova.** É uma amostra minúscula e o modelo foi calibrado em dados que se sobrepõem em parte (29 jogos de cantos). Também se testaram mercados do jogo todo (Under 3.5 golos): −12 a −20%, por isso ficaram fora.

## 5. Expectativa honesta
Com margens de 5 a 9% e um modelo de sinal fraco, o objetivo realista é ROI entre 0 e +5% a longo prazo, com muita variância. A v2 vai apostar pouco. Avaliar só com ≥ 50 apostas.
