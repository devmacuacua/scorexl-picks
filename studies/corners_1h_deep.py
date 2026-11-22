import sys,json,math,statistics as S
from collections import defaultdict
sys.path.insert(0,__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'scripts'))
import analyze_corners_1h as A
rows=A.load([2025,2026])
dom={'Premier League','La Liga','Serie A','Bundesliga','Ligue 1'}
print('jogos limpos',len(rows), {s:sum(r['season']==s for r in rows) for s in (2025,2026)})
T=lambda r:sum(r['corners_1h'])
# 1. base by season/league
for s in (2025,2026):
    rs=[r for r in rows if r['season']==s and r['league'] in dom]
    t=[T(r) for r in rs]; print(s,'dom n',len(rs),'media',round(S.mean(t),2),'var',round(S.pvariance(t),2),'O3.5',round(sum(x>3.5 for x in t)/len(t),3),'O4.5',round(sum(x>4.5 for x in t)/len(t),3),'O5.5',round(sum(x>5.5 for x in t)/len(t),3))
# by league 2 seasons
for l in sorted(dom|{'Champions League','Europa League','Conference League'}):
    t=[T(r) for r in rows if r['league']==l]
    if t: print(f"  {l:18s} n={len(t):4d} media={S.mean(t):.2f} O3.5={sum(x>3.5 for x in t)/len(t):.3f} O4.5={sum(x>4.5 for x in t)/len(t):.3f} O5.5={sum(x>5.5 for x in t)/len(t):.3f}")
# 2. team persistence 2025: split by date parity halves (first 19 vs last 19 games)
def team_games(season):
    g=defaultdict(list)
    for r in rows:
        if r['season']!=season or r['league'] not in dom: continue
        for i,tid,name in ((0,r['home_id'],r['home']),(1,r['away_id'],r['away'])):
            g[(tid,name)].append({'f':r['corners_1h'][i],'a':r['corners_1h'][1-i],'tot':T(r),'fft':r['corners_ft'][i],'aft':r['corners_ft'][1-i],'v':i})
    return g
g=team_games(2025)
for key in ('f','a','tot','fft'):
    xs=[];ys=[]
    for t,gs in g.items():
        if len(gs)<30: continue
        h=len(gs)//2; xs.append(S.mean(x[key] for x in gs[:h])); ys.append(S.mean(x[key] for x in gs[h:]))
    print('persistência 1ª vs 2ª metade época 2025',key,'corr',round(S.correlation(xs,ys),3),'n equipas',len(xs))
# 3. Model: team ratings shrunk; exp = league_mean * att_h * def_a * homeadv + ...
def evaluate(season,min_g=6,k=8,use_prior=None,ft_weight=0.0,label=''):
    out=[]
    hist=defaultdict(list)
    lg_hist=defaultdict(list)
    for r in rows:
        if r['season']!=season: continue
        L=r['league']; lm=S.mean(lg_hist[L]) if len(lg_hist[L])>=20 else 4.5
        hh=hist[r['home_id']]; aa=hist[r['away_id']]
        if len(hh)>=min_g and len(aa)>=min_g:
            def rate(h,key,prior):
                n=len(h); s=sum(x[key] for x in h)
                return (s+prior*k)/(n+k)
            hf=rate(hh,'f',lm/2); ha=rate(hh,'a',lm/2); af=rate(aa,'f',lm/2); aA=rate(aa,'a',lm/2)
            e=(hf+aA)/2+(af+ha)/2
            if ft_weight:
                hff=rate(hh,'fft',lm/0.47/2); haf=rate(hh,'aft',lm/0.47/2); aff=rate(aa,'fft',lm/0.47/2); aaf=rate(aa,'aft',lm/0.47/2)
                e2=((hff+aaf)/2+(aff+haf)/2)*0.47
                e=(1-ft_weight)*e+ft_weight*e2
            if use_prior is not None:
                pr=use_prior.get(r['home_id']),use_prior.get(r['away_id'])
            out.append((e,T(r),r,lm))
        for i,tid in ((0,r['home_id']),(1,r['away_id'])):
            hist[tid].append({'f':r['corners_1h'][i],'a':r['corners_1h'][1-i],'fft':r['corners_ft'][i],'aft':r['corners_ft'][1-i]})
        lg_hist[L].append(T(r))
    xs,ys=[o[0] for o in out],[o[1] for o in out]
    mae=S.mean(abs(x-y) for x,y in zip(xs,ys)); base=S.mean(abs(o[3]-o[1]) for o in out)
    print(f'{label} época {season} n={len(out)} corr={S.correlation(xs,ys):.3f} MAE={mae:.3f} vs média liga {base:.3f}')
    return out
for s in (2025,2026):
    for fw in (0,0.5,1.0):
        for k in (4,8,16):
            evaluate(s,k=k,ft_weight=fw,label=f'k={k} ftw={fw}')
# 4. buckets of model (best) vs O4.5 / O3.5 / O5.5 on 2025 dom + 2026
res=[]
for s in (2025,2026): res+=evaluate(s,k=8,ft_weight=0.5,label='escolhido')
bk=defaultdict(list)
for e,t,r,lm in res: bk[round(e*4)/4].append(t)
print('buckets esperado -> real, O3.5,O4.5,O5.5')
for k,v in sorted(bk.items()):
    if len(v)>=15: print(f'  {k:.2f} n={len(v):4d} real={S.mean(v):.2f} O3.5={sum(x>3.5 for x in v)/len(v):.3f} O4.5={sum(x>4.5 for x in v)/len(v):.3f} O5.5={sum(x>5.5 for x in v)/len(v):.3f}')
# 5. what if bet Over 4.5 @1.84 / Under 4.5 @1.87 / Over 3.5 @1.39 / Under 5.5 @1.44 by model thresholds
def sim(side,line,odd,cond):
    n=w=pl=0
    for e,t,r,lm in res:
        if not cond(e): continue
        win=(t>line) if side=='O' else (t<line)
        n+=1;w+=win;pl+=(odd-1) if win else -1
    return n,w,round(pl/n,3) if n else None
for side,line,odd in (('O',4.5,1.84),('U',4.5,1.87),('O',3.5,1.39),('U',5.5,1.44),('O',5.5,2.55),('U',3.5,2.7)):
    for thr in (4.0,4.5,5.0,5.25,5.5):
        c=(lambda e,t=thr:e>=t) if side=='O' else (lambda e,t=thr:e<=t-0.5)
        print('sim',side,line,'@',odd,'cond', ('exp>=' if side=='O' else 'exp<=')+str(thr if side=='O' else thr-0.5),sim(side,line,odd,c))
# 6. favourites: home team 1H corners when home much stronger (pts per game diff) — use season-to-date goal diff
print('--- equipa da casa favorita (dif. golos/jogo pré-jogo):')
hist=defaultdict(list); fav=defaultdict(list)
for r in rows:
    hh=hist[(r['season'],r['home_id'])]; aa=hist[(r['season'],r['away_id'])]
    if len(hh)>=6 and len(aa)>=6:
        d=S.mean(hh)-S.mean(aa)
        b='≥+1.0' if d>=1 else '+0.5..1' if d>=0.5 else '-0.5..0.5' if d>-0.5 else '-1..-0.5' if d>-1 else '≤-1'
        fav[b].append(r)
    hist[(r['season'],r['home_id'])].append(r['goals'][0]-r['goals'][1]); hist[(r['season'],r['away_id'])].append(r['goals'][1]-r['goals'][0])
for b in ('≥+1.0','+0.5..1','-0.5..0.5','-1..-0.5','≤-1'):
    v=fav[b]; hc=[r['corners_1h'][0] for r in v]; ac=[r['corners_1h'][1] for r in v]
    print(f'  {b:10s} n={len(v):4d} total={S.mean(T(r) for r in v):.2f} O4.5={sum(T(r)>4.5 for r in v)/len(v):.3f} casa={S.mean(hc):.2f} (O1.5 {sum(x>1.5 for x in hc)/len(v):.2f}, O2.5 {sum(x>2.5 for x in hc)/len(v):.2f}, O3.5 {sum(x>3.5 for x in hc)/len(v):.2f}) fora={S.mean(ac):.2f}')
# 7. game state: HT score effect
st=defaultdict(list)
for r in rows:
    gh,ga=r['goals_ht']
    if gh is None: continue
    k='0-0' if gh==ga==0 else 'empate com golos' if gh==ga else 'casa ganha' if gh>ga else 'fora ganha'
    st[k].append(T(r))
print('--- por resultado ao intervalo:',{k:(len(v),round(S.mean(v),2),round(sum(x>4.5 for x in v)/len(v),3)) for k,v in st.items()})
# 8. by kickoff month (early season vs later)
mo=defaultdict(list)
for r in rows: mo[r['date'][5:7]].append(T(r))
print('--- por mês:',{k:(len(v),round(S.mean(v),2)) for k,v in sorted(mo.items())})
# 9. 1H vs 2H share
h2=[sum(((x or {}).get('corners') or 0) for x in r['h2']) for r in rows]
print('média 1ª parte',round(S.mean(T(r) for r in rows),2),'2ª parte',round(S.mean(h2),2))
# 10. correlation 1H corners with 1H shots/xg (diagnostic)
