exec(open('/tmp/claude-0/d/link.py').read())
src=open('/tmp/claude-0/d/imp2.py').read().split("wb=openpyxl.Workbook()")[0].split("exec(open('/tmp/claude-0/d/link.py').read())")[1]
exec(src)
import openpyxl
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter as L
t=pd.read_pickle('tool_vlees.pkl'); t['plu']=t.plu.astype(int); t['bsku']=t.bsku.astype(str)
m=pd.read_pickle('m.pkl')
b2=bulk.copy(); i2=idx.copy()
for sk,d in ch.items():
    for f,(n,_) in d.items():
        if f=='Inv_Part_Vendor':
            if sk in set(b2.Inv_Sku): b2.loc[b2.Inv_Sku==sk,'pv']=n
            i2.loc[sk,f]=n
        if f=='Inv_Desc' and sk in set(b2.Inv_Sku): b2.loc[b2.Inv_Sku==sk,'Inv_Desc']=n
        if f=='Inv_VendorID' and sk in set(b2.Inv_Sku): b2.loc[b2.Inv_Sku==sk,'Inv_VendorID']=n
bk={}
for r in b2.itertuples():
    if r.pv: bk.setdefault(r.pv.lower(),[]).append(r.Inv_Sku)
bi2=b2.set_index('Inv_Sku')
link={}
for r in m.itertuples():
    rv=i2.loc[r.sku,'Inv_Part_Vendor']; rv='' if pd.isna(rv) else str(rv).strip()
    for k in (rv.lower(),lead(rv),trail(rv)):
        if k and k in bk: link[r.PLU]=bk[k][0]; break
m['bsku']=m.PLU.map(link)
COMP={3101,3612,3615,3691}
def vend(v): return {'VAN KOOTEN':'Van Kooten','DELI NOVA':'Deli Nova','DEELEN':'Deelen ZV','FOODS USA':'Foods USA','HHB':'HHB','ONE TIME':'One time','EIGEN PRODUCTIE':'Eigen productie'}.get(v,v)
def stripb(d):
    d=re.sub(r'^\s*Bulk\s*','',d); d=re.sub(r'^[^,]*\d[^,]*,\s*','',d) if re.match(r'^[A-Za-z0-9\-]+,',d) else d.lstrip(', ')
    return d
rows=[]
cnt=m.dropna(subset=['bsku']).groupby('bsku').size()
for r in m.sort_values(['bsku','PLU'],na_position='last').itertuples():
    desc=re.sub(r'\s+',' ',str(r.re_Inv_Desc)).strip()
    if isinstance(r.bsku,str):
        n=cnt[r.bsku]; typ='1-op-1' if n==1 else f'Splitser ({n}x)'
        pv=bi2.loc[r.bsku,'pv']; lastnr=str(pv)
        let=''
        if r.PLU in COMP: let='Samengesteld artikel (eigen productie): meerdere bulkbronnen, buiten correctie. Controleer.'
        if r.PLU in(3020,3025,3050,3508): let='Controleer part nr'
        rows.append([typ,vend(bi2.loc[r.bsku,'Inv_VendorID']),(int(pv) if str(pv).isdigit() else pv) if pv!='' else None,stripb(bi2.loc[r.bsku,'Inv_Desc']),int(r.bsku),r.PLU,int(r.sku),desc,let])
    else:
        why={3027:'Pastrami (One time): geen bulk-koppeling',3050:'Rolladeschijf: part nr ontbreekt',3025:'Prosciutto: geen bulk-item'}.get(r.PLU,'Leveranciers-artikelnr ontbreekt: aan te vullen')
        rows.append(['?',vend(r.re_Inv_VendorID),None,None,None,r.PLU,int(r.sku),desc,why])
df=pd.DataFrame(rows,dtype=object,columns=['Type','Bulk leverancier *','Bulk art.nr (lev.) *','Bulk artikel (inkoop) *','Bulk SKU (RetailEdge) *','Portie PLU *','Portie ART NR *','Portie omschrijving *','Let op'])
# types: ontbrekend type -> '?'; bulks met 1 PLU
wbk=openpyxl.Workbook(); ws=wbk.active; ws.title='Vlees (nieuw)'
ws.append(list(df.columns))
for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='1F3864')
for r in df.itertuples(index=False): ws.append(list(r))
for j,wd in enumerate([14,18,16,44,16,10,12,42,70],1): ws.column_dimensions[L(j)].width=wd
ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
for row in ws.iter_rows(min_row=2):
    if row[0].value=='?' or row[8].value:
        for c in row: c.fill=PatternFill('solid',fgColor='FFF2CC')
# verwijderen
wp=set(w.PLU)
g=t[~t.plu.isin(m.PLU)].drop_duplicates('plu')
w2=wbk.create_sheet('Uit oude tabel verwijderen')
w2.append(['Portie PLU','ART NR','Omschrijving','Oud bulk SKU','Reden'])
for c in w2[1]: c.font=Font(bold=True)
for r in g.itertuples():
    w2.append([r.plu,r.art,r.om,r.bsku,'Niet meer in weegschaal-lijst en/of niet meer in RE (opgeschoond)' if r.plu not in wp else 'Niet in vleesselectie (kaas/overig)'])
for j,wd in enumerate([10,12,40,26,70],1): w2.column_dimensions[L(j)].width=wd
# verschil
w3=wbk.create_sheet('Verschil met oude tabel')
w3.append(['Portie PLU','Omschrijving','Oude tabel: bulk SKU','Nieuw: bulk SKU','Nieuw: bulk artikel','Wijziging'])
for c in w3[1]: c.font=Font(bold=True)
tm=t.set_index('plu').bsku.to_dict()
for r in df.itertuples(index=False):
    p=r[5]; old=tm.get(p); new=r[4] if pd.notna(r[4]) else None
    if old is None: ch_='Nieuw in tabel'
    elif new is not None and old==str(int(new)): continue
    elif old.startswith('n.v.t'): ch_='Was 1-op-1 zonder bulk, krijgt nu bulk-item'
    else: ch_='Ander bulk-item'
    w3.append([p,r[7],old,new,r[3],ch_])
for j,wd in enumerate([10,40,26,16,44,44],1): w3.column_dimensions[L(j)].width=wd
S=wbk.create_sheet('Uitleg',0)
S['A1']='Voorstel nieuwe mappingtabel Vlees (tabblad "Vlees" in Genereer_PICS_import.xlsm)'; S['A1'].font=Font(bold=True,size=13)
txt=['Kolommen zijn gelijk aan het tabblad Vlees, dus plakken kan 1-op-1 vanaf rij 2 (oude rijen eerst leegmaken).',
'Gebaseerd op de RE-export van 4-11-2026 plus de import van 5-11-2026 (part nr koppeling).',
'Type: 1-op-1 = 1 bulk voor 1 PLU, Splitser (nx) = 1 bulk voor n PLU, zoals in het kaas-tabblad.',
'Geel = nog aan te vullen of controleren (Let op).',
'Bulk art.nr is leeg waar er nog geen leveranciersnummer is; de koppeling loopt dan via de Bulk SKU.',
f'Aantal rijen: {len(df)}; waarvan met bulk: {int(df["Bulk SKU (RetailEdge) *"].notna().sum())}; zonder bulk: {int(df["Bulk SKU (RetailEdge) *"].isna().sum())}.',
f'In de oude tabel staan {len(g)} PLU die niet meer in de vleeslijst zitten (tabblad "Uit oude tabel verwijderen").']
for i,x in enumerate(txt,3): S.cell(i,1,x)
S.column_dimensions['A'].width=130
P='/mnt/user-data/outputs/Vlees_mappingtabel_voorstel_2026_11_05.xlsx'; wbk.save(P)
print(len(df),df['Bulk SKU (RetailEdge) *'].notna().sum(),df.Type.value_counts().head(8),len(g),w3.max_row-1)
