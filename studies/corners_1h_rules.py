import sys,statistics as S
from collections import defaultdict
sys.path.insert(0,__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'scripts'))
import analyze_corners_1h as A
rows=A.load([2025,2026]); T=lambda r:sum(r['corners_1h'])
hist=defaultdict(list); G=[]
for r in rows:
    h=hist[(r['season'],r['home_id'])][-5:]; a=hist[(r['season'],r['away_id'])][-5:]
    if len(h)==5 and len(a)==5:
        e=(S.mean(x[0] for x in h)+S.mean(x[1] for x in a))/2+(S.mean(x[0] for x in a)+S.mean(x[1] for x in h))/2
        e1=(S.mean(x[2] for x in h)+S.mean(x[3] for x in a))/2+(S.mean(x[2] for x in a)+S.mean(x[3] for x in h))/2
        G.append((r,e,e1))
    hist[(r['season'],r['home_id'])].append((r['corners_ft'][0],r['corners_ft'][1],r['corners_1h'][0],r['corners_1h'][1]))
    hist[(r['season'],r['away_id'])].append((r['corners_ft'][1],r['corners_ft'][0],r['corners_1h'][1],r['corners_1h'][0]))
def test(name,cond,side,line=4.5,odd=1.85):
    out=[]
    for s in (2025,2026,None):
        v=[r for r,e,e1 in G if (s is None or r['season']==s) and cond(r,e,e1)]
        if not v: out.append('-');continue
        w=sum((T(r)>line) if side=='O' else (T(r)<line) for r in v)
        out.append(f"{len(v)}j {w/len(v):.1%} ROI {(w*(odd-1)-(len(v)-w))/len(v):+.1%}")
    print(f"{name:55s} | 2025: {out[0]:24s} | 2026: {out[1]:24s} | total: {out[2]}")
low={'Serie A','Ligue 1','Europa League'}; high={'Premier League','Bundesliga','La Liga','Champions League'}
test('Under 4.5 sempre (@1.85)',lambda r,e,e1:True,'U')
test('Over 4.5 sempre (@1.85)',lambda r,e,e1:True,'O')
test('Under 4.5 esperado jogo <9',lambda r,e,e1:e<9,'U')
test('Under 4.5 esperado jogo <9.5',lambda r,e,e1:e<9.5,'U')
test('Under 4.5 Serie A',lambda r,e,e1:r['league']=='Serie A','U')
test('Under 4.5 Serie A/Ligue1 + esperado <9.5',lambda r,e,e1:r['league'] in low and e<9.5,'U')
test('Under 4.5 esperado 1ªp (5j) <4',lambda r,e,e1:e1<4,'U')
test('Under 4.5 esperado jogo<9 e 1ªp<4.2',lambda r,e,e1:e<9 and e1<4.2,'U')
test('Over 4.5 esperado jogo >=11',lambda r,e,e1:e>=11,'O')
test('Over 4.5 PL/Bundes/LaLiga + esperado >=10.5',lambda r,e,e1:r['league'] in high and e>=10.5,'O')
test('Over 4.5 Premier League',lambda r,e,e1:r['league']=='Premier League','O')
test('Over 4.5 PL + esperado >=10.5',lambda r,e,e1:r['league']=='Premier League' and e>=10.5,'O')
test('Over 3.5 esperado jogo >=11 (@1.39)',lambda r,e,e1:e>=11,'O',3.5,1.39)
test('Under 5.5 esperado <9 (@1.44)',lambda r,e,e1:e<9,'U',5.5,1.44)
test('Under 3.5 esperado <8.5 (@2.70)',lambda r,e,e1:e<8.5,'U',3.5,2.70)
print('--- 29 jogos com linha real 1xBet: esperado jogo vs linha justa')
oi=A.odds_index()
for r,e,e1 in G:
    o=oi.get(r['fid'])
    if not o: continue
    fair=min(((abs(v['Over']-v['Under']),L) for L,v in o['lines'].items()))[1]
    u45=o['lines'].get(4.5,{}).get('Under')
    print(f"{r['home'][:14]:14s} esp.jogo {e:5.1f} esp.1ªp {e1:4.1f} | linha 1xBet {fair} | Under4.5 @{u45} | real {T(r)}")
