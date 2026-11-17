# B.League Japão (api-sports 56) — algoritmo

- **Calendário:** sábado e domingo (pares de jogos contra o mesmo adversário), às ~07h05–08h05 de Maputo; à quarta (e noutros dias úteis) às ~12h05.
- **Parâmetros:** σ 12, fator casa 2.25, w_market 0.65. Total médio: 170 (ajustado depois de ver resultados acima de 175; confirmar).
  - **Atenção:** a classificação da api-sports veio vazia (sem vitórias nem derrotas). Nesse caso o modelo usa só o mercado e ficam poucos palpites. Normal.
- **Perfil:** handicaps curtos do favorito em casa (até −7.5, fora até −4.5) e moneyline da casa com vantagem do modelo.
- **Regras extra:**
  - A partir de 2026-27 os 3 estrangeiros podem estar em campo ao mesmo tempo, por isso os ratings do início da época atrasam-se em relação à realidade.
  - Ao 2.º jogo do par, a equipa que perdeu o 1.º costuma reagir (efeito de ajuste): não apostar handicap grande no vencedor do 1.º jogo.
- **Lesões:** não há relatório oficial. Usa as páginas de jogo em bleague.jp (cinco inicial ~1 h antes), as redes dos clubes e o X.
