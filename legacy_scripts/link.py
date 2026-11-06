exec(open('/tmp/claude-0/d/an.py').read())
import re
def lead(s):
    s=s.strip()
    if ',' in s: return s.split(',',1)[0].strip().lower()
    return s.lower()
def trail(s):
    s=s.strip()
    return s.split(',',1)[1].strip().lower() if ',' in s else ''
bk={}   # key->list of bulk skus
for r in bulk.itertuples():
    if r.pv: bk.setdefault(r.pv.lower(),[]).append(r.Inv_Sku)
bi=bulk.set_index('Inv_Sku')
def find(repv):
    if not repv: return None,'leeg'
    k=repv.lower()
    if k in bk: return bk[k],'exact'
    l=lead(repv)
    if l and l in bk: return bk[l],'nr'
    t=trail(repv)
    if t and t in bk: return bk[t],'tekst'
    # text w/o number e.g. ', Flanksteak p/kg'
    for kk in bk:
        if t and not l and (kk in t or t in kk): return bk[kk],'tekst~'
    return None,'geen'
kaas=w.Lev.fillna('').str.startswith('Van Beek')
ret=w[w.inRE & ~kaas & ~w.PLU.isin([999999,9999])].copy()
res=[find(x) for x in ret.repv]
ret['bulks']=[r[0] for r in res]; ret['how']=[r[1] for r in res]
