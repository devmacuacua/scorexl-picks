# Futebol: regras v2 (reset de 25/11/2026)

O Francisco pediu um reset completo das regras e deu liberdade total para as refazer. Estas regras substituem as anteriores (v1). Os números que as justificam estão em `studies/football_reset.md`.

## Porque é que a v1 falhava
1. **Probabilidades sobreconfiantes.** A v1 pegava nas médias dos últimos 5 jogos, multiplicava por 0.46/0.45 e aplicava Poisson. O resultado eram P de 0.70 a 0.83 em jogos que, no histórico (2 114 jogos), acertam 52 a 60%. Exemplos: quando o modelo previa 5–5.5 cantos na 1.ª parte, a média real foi 4.75 e o O4.5 acertou 52% (a v1 dizia ~70%). Com ≥ 2 golos esperados na 1.ª parte, o O1.5 acertou ~40% (a v1 dizia ~62%).
2. **As médias de 5 jogos quase não preveem estes totais.** A correlação com o total real da 1.ª parte é de 0.09 a 0.10. A média da liga é quase tão boa como o modelo.
3. **Só Overs.** A 1xBet tende a pôr o Over um pouco caro (a margem pesa mais desse lado). Nos 57 jogos com odds reais, a 1xBet dava ao O1.5 da 1.ª parte 42% sem margem e a realidade foi 35%. No histórico foi 36%.
4. **Taças inflacionavam as médias** (jogos contra equipas de divisões inferiores).
5. **Amostra.** 17 apostas não chegam para julgar regra nenhuma. Na v1, cada derrota levava a mudar regras. Na v2 a regra fica fixa até haver amostra.

## Regras v2
**Mercados: SÓ JOGO INTEIRO** (decisão do Francisco a 25/11/2026). Todos são totais, nos dois sentidos:
- `goals_ft_over|under`: golos no jogo (1.5, 2.5, 3.5);
- `btts_over|under`: ambas marcam (over = Sim, under = Não);
- `corners_ft_over|under`: cantos no jogo (8.5, 9.5, 10.5, 11.5).

Os mercados de 1.ª e 2.ª parte (goals_1h, corners_1h, goals_2h, btts_1h) estão desativados em `MARKETS`, mas continuam calibrados e podem ser reativados. Linhas inteiras ou asiáticas não entram. Vitória, handicap e mercados por equipa ficam de fora, porque o modelo não sabe mais do que o mercado sobre a força das equipas. Liquidação aos 90 minutos mais descontos (sem prolongamento).

**Probabilidade** (`scripts/football_model.py`):
1. Taxa base da prova para a linha (Over), calculada em `data/study` (2 609 jogos limpos) e encolhida para a média geral com 150 jogos de peso (`data/meta/football_model.json`).
2. Ajuste do modelo: `logit P = logit(base) + w × (E − média)`. E = cantos ou golos esperados do jogo = (casa a favor + fora contra)/2 + (fora a favor + casa contra)/2, com os últimos jogos **sem taças nem particulares** e pelo menos 3 jogos com dados por equipa. O w foi ajustado no histórico e é pequeno de propósito (~0.1 por canto ou golo esperado).
3. Mistura com o mercado: **P = w × modelo + (1 − w) × 1xBet sem margem**, com w = 0.75 nas partes (1.ª/2.ª) e nos cantos da 1.ª parte, e w = 0.60 no jogo todo (golos, ambas marcam, cantos), onde o mercado é mais afinado.
4. **Filtro de desacordo:** se |P_modelo − P_1xBet| > 0.10 (em P Over), não entra. Quando o modelo discorda muito, quase sempre é porque o mercado sabe algo que ele não sabe (por exemplo, a diferença de força das equipas, que mexe muito nos golos). No backtest, este filtro passou o ROI de −17% para +14%, em amostras pequenas.

**Entrada:**
- passa o filtro de desacordo;
- P × odd real da 1xBet ≥ **1.05**;
- odd entre **1.40 e 2.60**;
- só com odd real em data/ (sem odd real não há palpite);
- **1 palpite por jogo** (o de maior P × odd), **máximo 3 por dia**;
- stake fixo de **0.5 u**, confidence "media". Não há "alta" nem 1 u até a v2 ter 100 apostas liquidadas com ROI positivo;
- `min_odds` = 1/P.

O "perfil" (super favorito contra equipa fraca, evitar dérbis) **deixa de ser regra**: no histórico não muda o resultado de forma útil (o favorito forte mexe pouco no total da 1.ª parte e o mercado já o desconta). Fica só como informação na razão.

**Picks [] é normal.** Num dia típico, a v2 entra em 0 a 3 jogos. Não forçar.

## Revisão (sem mexer na regra antes disto)
- Às **50 apostas v2**: ver o ROI de by_ruleset.v2 e by_market. Se um mercado estiver abaixo de −15% com ≥ 20 apostas, suspender esse mercado.
- Às **150 apostas v2**: recalibrar (`build`) com os dados novos de data/study e rever MIN_EV e W_MODEL.
- `build` volta a correr quando data/study for atualizado (workflow study.yml).

## Procedimento diário (tarefa das 08h54)
1. `python3 scripts/football_model.py settle D-1`: liquida picks/football/(D-1).json, revê pendentes antigos e reconstrói results/football/summary.json de raiz (by_ruleset, by_market, by_odds_source…). Os cantos da 1.ª parte vêm de `yesterday_results[].stats_1h_home/away` (half=true, desde 25/11) ou de data/study. Se não houver dados, o pick fica "pending". A web só serve como último recurso e, se o valor for encontrado aí, regista-se à mão no results com a fonte.
2. `python3 scripts/football_model.py picks D --write`: gera os palpites e o avoid. Escrever a note (fonte, hora dos dados, erros, alterações).
3. Se picks/football/D.json já existir, a regra é a mesma: corre picks e explica na note o que mudou.
4. Odd de liquidação: a odd real do pick (odds_ref), ou a odd que o Francisco disser que apostou (`odds_used`). Ambas contam como "real".
