# NBL Austrália (api-sports 1) — algoritmo

- **Calendário:** de quinta a domingo (às vezes quarta). Os jogos à noite são às ~10h30–13h30 de Maputo (Perth às 13h30, Nova Zelândia às 08h30); os de fim de semana à tarde são às ~06h–08h. Época regular até meados de fevereiro, finais em fevereiro/março. Há jornadas duplas no Natal (16–27/12).
- **Parâmetros:** σ 13, fator casa 2.75, total ~183 (a liga com mais pontos). Na NBL26, 1 em cada 3 jogos acabou por 15+ pontos.
- **Perfil:** handicap do favorito em casa até −9.5 (fora até −5.5). **Overs ligados:** só entram se o total do modelo for ≥ mercado + 4 (máximo 1 por dia, stake 0.5).
- **Regras extra:**
  - Viagens a Perth ou à Nova Zelândia para a equipa visitante pesam mais: não apostar no favorito visitante depois de uma viagem dessas em menos de 48 h.
  - Os "Next Stars" (prospetos da NBA) podem ter minutos geridos.
  - Cada equipa tem 3 estrangeiros: se faltar um estrangeiro titular do lado apostado, retira o palpite.
- **Lesões:** lista oficial em nbl.com.au (Out/Day-to-Day/TBC; atualizada à mão e pode atrasar) e versão anotada em basketball.com.au.
