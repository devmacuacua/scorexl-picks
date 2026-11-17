# Basket League Grécia (api-sports 45) — algoritmo

- **Calendário:** sábado e domingo, entre as 15h e as 21h de Maputo (a mesma hora da Grécia até 28/03/2027; depois a Grécia fica 1 h à frente). Playoffs em maio/junho.
- **Parâmetros:** σ 13, fator casa 3.75, total ~166, w_market 0.7.
- **Domínio de dois clubes:** em 2025-26, o Olympiacos fez 24-0 (+17.9 por jogo) e o Panathinaikos +13.4.
- **Perfil:**
  - Handicap do favorito em casa até −9.5 (exclui quase sempre o Olympiacos e o Panathinaikos).
  - **Azarão com pontos** quando o favorito tem linha ≥ 15 (dog_points_min). Contra Olympiacos e Panathinaikos com linhas de −20 a −30, eles rodam o plantel e há muito tempo de lixo.
  - No clássico (Panathinaikos–Olympiacos), só moneyline, e só se o script o propuser.
- **Regras extra:**
  - Depois de jogo da Euroliga, os dois grandes poupam titulares contra equipas pequenas: isso favorece o azarão com pontos.
  - Sanções de 2026-27: 2 pontos retirados a cada um dos grandes; Tyrique Jones suspenso por 7 jogos e Kendrick Nunn por 2. Cada um dos grandes joga 1 jogo à porta fechada (sem fator casa nesse jogo).
- **Lesões:** Gazzetta.gr, SDNA, Eurohoops GR.
