# Liga ACB Espanha (api-sports 117) — algoritmo

- **Calendário:** sobretudo sábado e domingo, entre as 13h e as 22h de Maputo (às vezes há jornadas a meio da semana). Época de setembro a maio, playoffs até junho.
- **Parâmetros:** σ 12, fator casa 4.0 (fonte: relatório estatístico ACB, +4.06), total ~176, w_market 0.75 (mercado eficiente nos grandes clubes).
- **Perfil:** handicap do favorito em casa até −8.5 (fora até −4.5).
- **Regras extra:**
  - Real Madrid, Barça, Valencia, Baskonia (e outros com competição europeia) depois de semana dupla europeia: retira os handicaps a favor deles. Fica atento a descanso de titulares.
  - Equipas pequenas em casa contra clubes da Euroliga cansados podem ter valor com pontos, mas o script não propõe isso: não acrescentes.
- **Lesões:** acb.com (pré-jogo), comunicados dos clubes, Gigantes del Basket, Marca/AS.
