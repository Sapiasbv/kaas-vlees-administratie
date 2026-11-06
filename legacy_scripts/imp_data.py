import pickle,pandas as pd,glob,sys,datetime as dt
sys.path.insert(0,'/tmp/claude-0/b')
from data import lines
R=pickle.load(open('/tmp/claude-0/c/res.pkl','rb')); w=R['w'].copy(); v=R['v'].copy(); gapRE=R['gapRE']
U="/root/.claude/uploads/409f47d1-0774-59fa-8af2-ef9852bec079/"
inv=pd.read_csv(glob.glob(U+"*inventory*")[0],dtype=str,low_memory=False,encoding='cp1252')
main=inv[inv.Loc_Settings_LocID=="Main"].set_index('Inv_Sku')
v['BULKs']=v.BULK.map(lambda x: None if pd.isna(x) else str(int(x)))
bp=v.dropna(subset=['BULKs']).groupby('PLU').BULKs.first().to_dict()
ba={}
for r in v.dropna(subset=['BULKs']).itertuples(): ba[str(r.artlev).strip().lower()]=r.BULKs
w['Leverancier']=w['Leverancier'].fillna('(geen leverancier)')
w['best']=w['Bestelnummer leverancier'].map(lambda x: '' if pd.isna(x) else (str(int(x)) if isinstance(x,(int,float)) else str(x).strip()))
oldart=v.groupby('PLU').artlev.first().to_dict()
def fixbest(r):
    b=r.best
    if b and not any(ch.isdigit() for ch in b):
        o=str(oldart.get(r.PLU,'')).strip()
        if o.replace('.0','').isdigit(): return o.replace('.0','')
    return b
w['best']=w.apply(fixbest,axis=1)
w['bulk']=w.apply(lambda r: bp.get(r.PLU) or ba.get(r.best.lower()),axis=1)
w['inRE']=~w.PLU.isin(gapRE.PLU)
VEND={'Van Kooten':'VAN KOOTEN','Deli Nova':'DELI NOVA','Deelen ZV':'DEELEN','Deelen LV':'DEELEN - LV','Foods USA':'FOODS USA','HHB':'HHB','One time':'ONE TIME','Eigen productie':'EIGEN PRODUCTIE','(geen leverancier)':''}
GRP={'Gevogelte':('02. Slagerij vers','0201: Kip'),'Rundvlees':('02. Slagerij vers','0202: Rund'),'Varkensvlees':('02. Slagerij vers','0203: Varkensvlees'),
     'Vleeswaren':('03. Vleeswaren','0301: Vleeswaren vers gesneden'),'Vegetarisch':('02. Slagerij vers','0205: Vega/vleesvervangers'),'Vlugklaar':('02. Slagerij vers','0406: Convenience en overige gekoeld')}
# latest invoice price per kg
last={}
for l in sorted(lines,key=lambda x:x['date']):
    if l['type']!='Factuur' or l['kg']<=0 or l['amount']<=0: continue
    last[(l['sup'],str(l['code']).lower())]=(round(l['amount']/l['kg'],4),'EUR' if l['sup']=='Van Kooten' else 'USD',l['date'],l['desc'])
def lastprice(best,lev):
    for sup in ('Van Kooten','DeliNova'):
        k=(sup,best.lower())
        if k in last and ((sup=='Van Kooten')==(lev=='VAN KOOTEN') or lev in ('ONE TIME','') ): return last[k]
    return None
def clean(n): 
    import re
    n=re.sub(r',?\s*p/(kg|st|lg)\b\.?','',str(n)).strip(); n=re.sub(r'\s+',' ',n); return n.strip(' ,')
nb=w[w.bulk.isna()&(w.PLU!=9999)&(~w.PLU.isin([3090,3091]))&w.inRE].copy()
rows=[]
def dc(plus):
    cs=[];ds=[]
    for p in plus:
        s=str(200000+p)
        if s in main.index: cs.append(main.loc[s,'Inv_ClassID']); 
    cls=pd.Series(cs).mode().iloc[0] if cs else None
    return cls
def build(group,soort,bestelnr):
    g=group.sort_values('PLU'); plus=list(g.PLU)
    levs=[l for l in g.Leverancier if l!='One time'] or list(g.Leverancier)
    lev=VEND.get(pd.Series(levs).mode().iloc[0],'')
    grp=g['Groep text'].iloc[0]; cls=dc(plus) or GRP[grp][1]
    dept='03. Vleeswaren' if cls[:4] in ('0301','0303') else '02. Slagerij vers'
    # name
    nm=None
    if bestelnr:
        o=v[v.artlev.astype(str).str.strip().str.lower()==bestelnr.lower()]
        o=o[o.naamlev.notna()]
        if len(o): nm=str(o.naamlev.iloc[0]).strip()
        lp=lastprice(bestelnr,lev)
        if nm is None and lp: nm=lp[3]
    else: lp=None
    if nm is None: nm=clean(g.Artikel.iloc[0])
    nm=clean(nm)
    desc=f"Bulk {bestelnr}, {nm}" if (bestelnr and any(ch.isdigit() for ch in bestelnr)) else f"Bulk, {nm}"
    # prijsbron: hoofd-PLU = laagste PLU met RE-artikel (voorkeur niet 'One time')
    cand=[(p,str(200000+p)) for p in plus if str(200000+p) in main.index]
    pref=[c for c in cand if g[g.PLU==c[0]].Leverancier.iloc[0]!='One time'] or cand
    rp=None
    if pref:
        p0,s0=pref[0]; r0=main.loc[s0]
        f=lambda k: float(r0[k]) if pd.notna(r0[k]) else None
        if (f('Inv_Cost_Last') or 0)>0:
            vals=[f('Inv_Cost_Last'),f('Inv_Loc_Price_Was'),f('Inv_Loc_Price1'),f('Inv_Loc_Price2'),f('Inv_Loc_Price3'),f('Inv_Loc_Price4'),f('Inv_Loc_Price5')]
            diff=len({round(float(main.loc[s,'Inv_Cost_Last']),2) for _,s in cand})>1 or len({round(float(main.loc[s,'Inv_Loc_Price1']),2) for _,s in cand})>1
            rp=dict(plu=p0,sku=s0,vals=vals,diff=diff)
    return dict(rp=rp,soort=soort,desc=desc[:250],lev=lev,levw=", ".join(sorted(set(g.Leverancier))),best=bestelnr,plus=plus,art="; ".join(g.Artikel),dept=dept,cls=cls,lp=lp,
                retailRE=sum(1 for p in plus if str(200000+p) in main.index))
A=nb[(nb.best!='')&(nb.best.str.lower()!='samengesteld')&(nb.Leverancier!='Eigen productie')]
for b,g in A.groupby(A.best.str.lower()): rows.append(build(g,'A bulk met bestelnr',g.best.iloc[0]))
rows.sort(key=lambda r:(r['lev'],r['best']))
Brows=[]
for r in nb[(nb.best=='')&(nb.Leverancier!='Eigen productie')].sort_values('PLU').itertuples():
    Brows.append(build(nb[nb.PLU==r.PLU],'B bulk, bestelnr ontbreekt',''))
Crows=[]
for r in nb[(nb.Leverancier=='Eigen productie')|(nb.best.str.lower()=='samengesteld')].sort_values('PLU').itertuples():
    Crows.append(build(nb[nb.PLU==r.PLU],'C samengesteld / eigen productie',''))
allb=rows+Brows+Crows
# missing PLU articles
mis=w[~w.inRE&(~w.PLU.isin([9999,3090,3091]))].sort_values('PLU')
if __name__=="__main__":
    print(len(rows),len(Brows),len(Crows),len(mis))
    pd.set_option('display.width',250,'display.max_colwidth',60,'display.max_rows',200)
    d=pd.DataFrame(allb); print(d[['soort','desc','lev','best','dept','cls','lp','retailRE']].to_string())
    print(mis[['PLU','Artikel','Leverancier','Groep text']])
