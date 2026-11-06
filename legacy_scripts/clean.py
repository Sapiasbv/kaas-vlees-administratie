import pandas as pd, glob, openpyxl
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter as L
U="/root/.claude/uploads/409f47d1-0774-59fa-8af2-ef9852bec079/"
i=pd.read_csv(glob.glob(U+"*inventory*")[0],dtype=str,low_memory=False,encoding='cp1252')
i['q']=pd.to_numeric(i.Inv_Quan,errors='coerce').fillna(0)
w=pd.read_excel(glob.glob(U+"*Weegschaal*")[0]); W=set(w.PLU.astype(int))
v=pd.read_excel(glob.glob(U+"*Vlees_en*")[0],header=1)
v.columns=['lev','artlev','naamlev','naamRE','inkoop','landed','x','PLU','ART','BULK','ITEM','VK','marge']
v['xlrow']=v.index+3
p=i.pivot_table(index=['Inv_Sku','Inv_Desc','Inv_DepartID','Inv_ClassID','Inv_VendorID'],columns='Loc_Settings_LocID',values='q',aggfunc='sum').reset_index()
p.columns.name=None; p['Main']=p['Main'].fillna(0); p['Sapias']=p['Sapias'].fillna(0)
p['cls']=p.Inv_ClassID.str[:4]
bulk_old=set(v.BULK.dropna().astype('int64').astype(str))
HAMPLU={'2024700084939':3090,'2024700084946':3091}
MEAT={'0201','0202','0203','0204','0205','0301','0303','0603'}
six=p[(p.Inv_Sku.str.len()==6)&p.Inv_Sku.str.startswith('20')].copy(); six['PLU']=six.Inv_Sku.astype(int)-200000
A=six[(~six.PLU.isin(W))&six.cls.isin(MEAT)&six.Inv_DepartID.isin(['02. Slagerij vers','03. Vleeswaren','14. Hardlopers'])].copy()
A['reden']='Weegschaal-artikel (PLU '+A.PLU.astype(str)+') staat niet in weegschaal assortiment'
B=six[(~six.PLU.isin(W))&(six.Inv_DepartID=='02. Slagerij vers')&(~six.cls.isin(MEAT))].copy()
B['cat']='Salade / fruit / zuivel (eigen productie)'; B['reden']='PLU '+B.PLU.astype(str)+' niet in weegschaal assortiment (lijst bevat alleen vlees)'
dep=['02. Slagerij vers','03. Vleeswaren','03. Vleeswaren, kaas en deli']
thir=p[(p.Inv_Sku.str.len()>=7)&p.Inv_DepartID.isin(dep)&(~p.Inv_Sku.isin(bulk_old))&(~p.Inv_Sku.isin(HAMPLU))].copy()
def cat(r):
    d=r.Inv_Desc.lower(); c=r.cls
    if r.Inv_VendorID=='ONE TIME' and ('divers' in d): return 'Verzamelartikel (Diverse ...)'
    if c=='0204' or any(k in d for k in ['garnaal','mossel','makreel','surimi','zalm','oester']): return 'Vis'
    if any(k in d for k in ['vivera','vega','vegan']): return 'Vega (Vivera e.d.)'
    if c in('0405','0302') or any(k in d for k in ['kaas','gouda','pate plak','pate']): return 'Kaas / paté voorverpakt'
    return 'Vlees voorverpakt / overig'
thir['cat']=thir.apply(cat,axis=1); thir['reden']='Barcode-artikel, geen weegschaal-artikel; staat niet in weegschaal assortiment'
C=thir
D=v[~v.PLU.isin(W)].copy()
# assertions
assert not A.PLU.isin(W).any() and not B.PLU.isin(W).any() and not D.PLU.isin(W).any()
# bulk table
rows=[]
b=v[v.BULK.notna()].copy(); b['BULK']=b.BULK.astype('int64').astype(str)
for k,g in b.groupby('BULK'):
    r=p[p.Inv_Sku==k]
    pl=sorted(g.PLU.tolist())
    rows.append(dict(sku=k,naam=g.naamRE.iloc[0],inre=len(r)>0,main=float(r.Main.iloc[0]) if len(r) else None,sap=float(r.Sapias.iloc[0]) if len(r) else None,
      plus_all=len(pl),plus_w=[x for x in pl if x in W],plus_notw=[x for x in pl if x not in W]))
BK=pd.DataFrame(rows)
# weegschaal gaps
RE_PLU=set(six.PLU)|{3090,3091}  # ham di pasku via 13-digit
gapRE=w[~w.PLU.isin(RE_PLU)]; gapOld=w[~w.PLU.isin(set(v.PLU))]
print(len(A),len(B),len(C),len(D),len(BK),len(gapRE),len(gapOld))
print(C.cat.value_counts()); print(BK[~BK.inre][['sku','naam']]); print(A[(A.Main!=0)|(A.Sapias!=0)][['Inv_Sku','Inv_Desc','Main','Sapias']])
import pickle; pickle.dump(dict(A=A,B=B,C=C,D=D,BK=BK,gapRE=gapRE,gapOld=gapOld,w=w,v=v),open('/tmp/claude-0/c/res.pkl','wb'))
