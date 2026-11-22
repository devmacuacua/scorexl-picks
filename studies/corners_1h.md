# Estudo: cantos na 1.ª parte (futebol) — 22/11/2026

Dados: `data/study/corners_1h_2025.json` (5 grandes ligas, época 2025/26 completa) e `corners_1h_2026.json` (5 ligas + UCL/UEL/UECL, até 22/11/2026), recolhidos com `fixtures/statistics?half=true` (workflow `study.yml`). Após limpeza (1.ª + 2.ª parte = total), 2 609 jogos. Odds reais 1xBet do mercado "Total Corners (1st Half)" em 29 jogos (data/football, 20-21/11).

## Números base
- Média 4.49 cantos na 1.ª parte (2.ª parte 5.09); 47% dos cantos do jogo.
- Over 3.5: 64% · Over 4.5: 47% · Over 5.5: 30%.
- Por liga (média / O4.5): Premier 4.77 / 53% · La Liga 4.58 / 49% · Bundesliga 4.50 / 48% · Champions 4.50 / 49% · Ligue 1 4.44 / 46% · Europa 4.32 / 43% · Serie A 4.16 / 41%.
- 1xBet: linha quase sempre 4.5 ou 4.75 (Over 4.5 ~1.84, Under 4.5 ~1.87), margem ~8.5%. A linha varia pouco de jogo para jogo.

## Previsibilidade
- Total da 1.ª parte é muito ruidoso: correlação modelo-real ~0.10-0.17; o modelo por equipas mal bate a média da liga.
- O que é estável: cantos A FAVOR de cada equipa (persistência 0.52 por 1.ª parte; 0.67 no jogo inteiro). O total por jogo é pouco estável (0.22).
- Favorito forte em casa (dif. golos/jogo ≥ +1): total 1.ª parte 4.72 (O4.5 52%); cantos da equipa da casa 3.26 (O1.5 82%, O2.5 60%).
- Resultado ao intervalo quase não muda o total da 1.ª parte.

## Regras testadas (Under 4.5 @1.85 / Over 4.5 @1.85; esperado do jogo = método atual, últimos 5 jogos)
| Regra | 2025 | 2026 | Total |
|---|---|---|---|
| Over 4.5 sempre | 47.1%, ROI −12.9% | 44.7%, −17.3% | −13.7% |
| Under 4.5 sempre | 52.9%, −2.1% | 55.3%, +2.3% | −1.3% |
| **Under 4.5 se esperado jogo < 9** | 57.0%, +5.5% (491) | 62.4%, +15.4% (93) | **57.9%, +7.1% (584)** |
| Under 4.5 Serie A/Ligue 1 + esperado < 9.5 | 57.7%, +6.8% | 65.0%, +20.3% | 58.9%, +9.1% (475) |
| Under 5.5 se esperado < 9 (@1.44) | 74.7%, +7.6% | 78.5%, +13.0% | 75.3%, +8.5% |
| Over 4.5 se esperado jogo ≥ 11 (regra atual) | 51.6%, −4.6% | 57.1%, +5.7% | 52.9%, −2.2% |
| Over 4.5 Premier + esperado ≥ 10.5 | 57.4%, +6.2% | 54.5% (11) | 57.1%, +5.7% (126) |
Nos 29 jogos com odds reais, Under 4.5 com esperado < 9 deu 6-4 (+10.6%) — a 1xBet baixa a odd do Under para ~1.71-1.75 em alguns destes jogos.

## Conclusões
1. O valor está no UNDER, não no Over. Over da 1.ª parte perde ~14% em média com a margem da 1xBet.
2. Regra candidata (fase de teste): Under 4.5 cantos 1.ª parte quando o esperado de cantos do jogo < 9 (ideal Serie A, Ligue 1, Europa League), só com odd Under ≥ 1.80 (break-even 57.9% → 1.73). Se a 1xBet puser a linha em 4.25, não entrar (Under 4.25 vale menos).
3. Abandonar a regra "Over 4.5 1.ª parte se esperado ≥ 11": −2% no histórico.
4. A explorar: cantos da equipa favorita na 1.ª parte (mercado por equipa) — precisa das odds desse mercado (não recolhidas ainda).
