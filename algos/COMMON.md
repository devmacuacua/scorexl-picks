# Ligas de basquetebol (fora da NBA): procedimento comum

Cada liga tem a sua tarefa diária e o seu algoritmo. Os parâmetros numéricos estão em `algos/params.json`; as regras e particularidades da liga estão em `algos/<liga>.md`. As chaves das ligas são: euroleague, eurocup, nbl, bleague, cba, acb, bsl, gbl, aba.

D = data de Maputo (UTC+2) no momento da corrida. Os ficheiros são:
- Dados: `data/<liga>/D.json`
- Palpites: `picks/<liga>/D.json`
- Resultados: `results/<liga>/<dia>.json` e `results/<liga>/summary.json`

## Passos

1. **Clonar.** `git clone --depth 1 https://github.com/devmacuacua/scorexl-picks repo` (timeout generoso).
2. **Recolha fresca.** Dispara a GitHub Action com a ferramenta MCP `actions_run_trigger`: method "run_workflow", owner devmacuacua, repo scorexl-picks, workflow_id "apisports.yml", ref "main", inputs {"only": "<liga>"}.
   - Faz `git pull` a cada 15 s, até 4 minutos, até `data/<liga>/D.json` ter um `generated_at` dos últimos 30 min.
   - Se não chegar, usa o ficheiro mais recente e diz isso na note.
3. **Liquidar.** Corre `python3 scripts/basket_settle.py <liga>`.
   - O script liquida todos os dias anteriores ainda por processar, usando `recent_results` (D-1 a D-3).
   - Se um dia ficar "pending" (falta resultado), procura o resultado final na web (site oficial da liga, ESPN, Flashscore ou Eurohoops). Depois edita `results/<liga>/<dia>.json` e o summary com as mesmas regras do script: handicap ganha se margem + linha > 0, prolongamento incluído.
4. **Analisar.** Corre `python3 scripts/basket_analyze.py <liga> --write`. O script grava o rascunho `picks/<liga>/D.json` e mostra os números de cada jogo.
   - **Margem esperada:** combina a linha do mercado (Asian Handicap 1xBet com odds mais equilibradas) com o modelo da classificação (saldo por jogo, regredido à média, mais o fator casa).
   - **Filtros:** odd entre 1.80 e 2.00, P×odd ≥ 1.03 (moneyline ≥ 1.05), favorito ≥ fav_min, linha ≤ máximo da liga, favorito sem back-to-back.
   - **Limites:** no máximo 3 palpites e 1 Over por dia; stake de 0.5.
5. **Lesões (obrigatório, antes de publicar).** Para cada palpite do rascunho, pesquisa na web as lesões e baixas das duas equipas, usando as fontes da liga em `algos/<liga>.md`.
   - Retira o palpite se a estrela do lado apostado (ou de qualquer equipa, no caso de um Over) estiver fora ou em dúvida, ou se se aplicar uma regra específica da liga (rotação depois de jogo europeu, estrangeiros, etc.). Passa-o para "avoid" com o motivo.
   - Também podes retirar por bom senso (notícia relevante), mas nunca acrescentes palpites que o script não propôs.
   - Se a web falhar, mantém os palpites, mas escreve a limitação na note.
6. **Note.** Escreve no `picks/<liga>/D.json` o `generated_at` usado, as lesões relevantes e as decisões. Remove o campo `ev` dos palpites e mantém `game_id`, `side` e `line`, que a liquidação usa.
   - Sem jogos hoje: não cries ficheiro de palpites. Faz commit só se houve liquidação.
7. **Publicar.** `git add -A`, commit "<LIGA> D: picks + resultados" com autor Claude <noreply@anthropic.com>, `git fetch origin main`, rebase se for preciso, push para main.
8. **Notificar** (PushNotification, com `<routine_summary>`) só se houver palpites hoje, apostas liquidadas ou uma falha (recolha, push). Sem nada disto, não notifiques.
   - Conteúdo: resultados liquidados e acumulado da liga (apostas, hit rate, lucro, ROI); palpites (hora de Maputo, jogo, palpite, odd 1xBet, odd mínima, P, P×odd, razão); jogos a evitar mais relevantes; falhas.
   - Termina com: "Confirmar na 1xBet odd ≥ odd mínima e lesões; só simples, 100-150 MT ou 3% da banca."

## Formato de picks/<liga>/D.json

{"date","sport","league_key","note","picks":[{"match":"Casa vs Fora","tipoff_maputo","game_id","market":"handicap|moneyline|total_over","selection","side":"home|away|total","line","min_odds","odds_ref","bookmaker","win_prob","confidence":"media","stake_units":0.5,"reason"}],"avoid":[{"match","reason"}]}

## Fase de teste

Todas as ligas começam com stake de 0.5 e confiança "media". O stake só sobe para 1 numa liga com pelo menos 30 apostas e ROI > 0 no summary, e a decisão é do Francisco. Ajustes de parâmetros: edita `algos/params.json` e regista o motivo em `algos/<liga>.md`.
