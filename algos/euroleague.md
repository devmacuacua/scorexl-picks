# Euroliga (api-sports 120) — algoritmo

- **Calendário:** de terça a sexta, entre as 18h e as 22h45 de Maputo (as semanas duplas têm jornadas à terça/quarta e à quinta/sexta). Época regular até 16/04/2027, play-in a 20 e 23/04, playoffs de 27/04 a 12/05, Final Four de 28 a 30/05.
- **Mercado:** é o mais eficiente das ligas seguidas (margem da casa de ~5–6%). Pesa 80% no algoritmo (w_market 0.8).
- **Parâmetros:** σ 11.5, fator casa 3.5 pts (fonte: modelo bayesiano 2020-25), total médio ~171.
- **Perfil:** handicaps curtos de favoritos em casa (até −6.5) e fora (até −4.5), ou moneyline da casa em jogos equilibrados quando o modelo dá vantagem (P×odd ≥ 1.05). Evitar linhas grandes. Overs desligados até haver histórico.
- **Regras extra (aplicar na revisão de lesões):**
  - Semana dupla: retira o palpite se a equipa apostada jogou há 2 dias ou menos fora de casa, com viagem longa.
  - Jogo "em casa" em campo neutro (por exemplo, equipas israelitas a jogar fora do país) → sem fator casa: retira handicaps dessa equipa.
  - Dubai é novo na liga: o fator casa é incerto.
- **Lesões:** relatório oficial de lesões da Euroliga (euroleaguebasketball.net, publicado por jogo), Eurohoops ("Injury report round N"), @EurohoopsNet, @Sportando.
