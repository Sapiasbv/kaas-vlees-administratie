exec(open('/tmp/claude-0/d/link.py').read())
import openpyxl
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter as L
T=openpyxl.load_workbook(U+"3c35f4f9-RetailEdge_CSV_Inventory_Import_Template_with_Notes_2.xlsx")["Sheet1"]
hdr=[c.value for c in T[1]]
MAP={'User Field 4':'Text on Price Tag','CustomSubTotal1':'EBT','CustomSubTotal2':'DUFB'}
idx=main.set_index('Inv_Sku')
ch={}   # sku -> {field: (new, reason)}
def setc(sku,f,new,why):
    ch.setdefault(sku,{})[f]=(new,why)
rp=lambda p: idx.loc[str(200000+p),'Inv_Part_Vendor']
setc('2024700092798','Inv_Part_Vendor','210405','Typfout 21405 -> 210405 (PLU 3606, 3607)')
for p,sk in {5802:'2024700106433',5814:'2024700106440',4610:'2024700106426',4300:'2024700106402',4400:'2024700106419',7900:'2024700106457',3691:'2024700106495',3002:'2024700106228'}.items():
    setc(sk,'Inv_Part_Vendor',rp(p),f'Part nr overgenomen van retail {200000+p}')
setc('203600','Inv_Part_Vendor','210403, Flanksteak p/kg','Nummer toegevoegd, bulk 210403')
setc('203647','Inv_Part_Vendor','3, MAG MET varkens dv','Nummer toegevoegd, bulk 3')
setc('203643','Inv_Part_Vendor','varkens trimmings/snipper','Exact gelijk aan bulk 2024700106211')
for p in (3641,3651,3652): setc(str(200000+p),'Inv_Part_Vendor','210190, Rundersnippers 80/20 Kooten','Nummer toegevoegd, bulk 210190')
setc('203002','Inv_VendorID','DEELEN','Weegschaal: Deelen ZV')
for p in (3101,3612,3615,3691): setc(str(200000+p),'Inv_VendorID','EIGEN PRODUCTIE','Weegschaal: Eigen productie; bulk EIGEN PRODUCTIE')
for p in (3562,3563,3564): setc(str(200000+p),'Inv_VendorID','FOODS USA','Weegschaal: Foods USA; bulk FOODS USA')
for sk in ('2024700092651','2024700092668'): setc(sk,'Inv_ClassID','0203: Varkensvlees','Retail grillworst staat op 0203')
setc('2024700106112','Inv_ClassID','0201: Kip','Kiphamburgers')
wb=openpyxl.Workbook(); ws=wb.active; ws.title='Import bijwerken'
ws.append(hdr)
for c in ws[1]: c.font=Font(bold=True)
def val(m,h):
    k=MAP.get(h,h)
    if k not in m.index: return None
    v=m[k]
    if pd.isna(v): return None
    if h in('Inv_Loc_Taxable','Inv_Loc_DenySales','Inv_Cost_Dynamic','CustomSubTotal1','CustomSubTotal2','CustomSubTotal3'): return str(v).lower()=='true'
    if h in('Inv_Sku','Inv_ItemID','Inv_Part_Vendor','Inv_UPC1','Inv_UPC2','Inv_Desc'): return str(v)
    try: return float(v)
    except: return str(v)
order=sorted(ch)
for sk in order:
    m=idx.loc[sk]; row=[]
    for h in hdr:
        v=val(m,h)
        if h=='Inv_Sku': v=sk
        if h in ch[sk]: v=ch[sk][h][0]
        row.append(v)
    ws.append(row)
for j,h in enumerate(hdr,1): ws.column_dimensions[L(j)].width=18
ws.column_dimensions['B'].width=42; ws.freeze_panes='C2'
inf=wb.create_sheet('Info')
inf.append(['Regel','Inv_Sku','Omschrijving','Veld','Nu in RE','Nieuw','Reden'])
for c in inf[1]: c.font=Font(bold=True)
for i,sk in enumerate(order,2):
    for f,(new,why) in ch[sk].items():
        inf.append([i,sk,idx.loc[sk,'Inv_Desc'],f,idx.loc[sk,f] if pd.notna(idx.loc[sk,f]) else '(leeg)',new,why])
for j,wd in enumerate([7,16,44,15,40,40,60],1): inf.column_dimensions[L(j)].width=wd
# open
o=wb.create_sheet('Nog open (leeg gelaten)')
o.append(['RE art. nr','Artikel','Vendor RE','Wat ontbreekt','Opmerking'])
for c in o[1]: c.font=Font(bold=True)
m=pd.read_pickle('m.pkl')
for r in m[(m.repv=='')&m.reden.fillna('').str.startswith('Retail part nr leeg')].itertuples():
    o.append([r.sku,r.Artikel,r.re_Inv_VendorID,'Vendor part nr op retail en op bulk','Zoek leveranciersnummer, vul op beide in']) 
o.append(['203050','Rolladeschijf','ONE TIME','Part nr','Weegschaal zegt 2098 (Buik): klopt dat?'])
o.append(['203020','Katenspek','VAN KOOTEN','Part nr','RE 2114 of weegschaal/bulk 3020?'])
o.append(['203508','Kipshoarma','DELI NOVA','Part nr','Weegschaal 310007, RE 310006'])
o.append(['203025','Prosciutto Crudo','ONE TIME','Bulk','Geen bulk-item; weegschaal bestelnr 93 klopt niet'])
for j,wd in enumerate([12,42,18,36,60],1): o.column_dimensions[L(j)].width=wd
P='/mnt/user-data/outputs/RetailEdge_Import_Bijwerken_Koppeling_2026_11_04.xlsx'
wb.save(P); print(len(order),sum(len(v) for v in ch.values()))
# simulate link
import copy
b2=bulk.copy(); i2=idx.copy()
for sk,d in ch.items():
    for f,(n,_) in d.items():
        if sk in b2.Inv_Sku.values and f=='Inv_Part_Vendor': b2.loc[b2.Inv_Sku==sk,'pv']=n
        if f=='Inv_Part_Vendor': i2.loc[sk,f]=n
bk={}
for r in b2.itertuples():
    if r.pv: bk.setdefault(r.pv.lower(),[]).append(r.Inv_Sku)
mm=m.copy(); ok=0; bad=[]
for r in mm.itertuples():
    rv=i2.loc[r.sku,'Inv_Part_Vendor']; rv='' if pd.isna(rv) else str(rv).strip()
    hit=bool(rv) and (rv.lower() in bk or lead(rv) in bk or (trail(rv) in bk))
    if hit: ok+=1
    else: bad.append((r.PLU,r.Artikel,rv))
print(ok,len(mm)); print(bad)
used=set()
for r in mm.itertuples():
    rv=i2.loc[r.sku,'Inv_Part_Vendor']; rv='' if pd.isna(rv) else str(rv).strip()
    for k in (rv.lower(),lead(rv),trail(rv)):
        if k in bk: used|=set(bk[k]); break
print(len(b2),len(used)); print(b2[~b2.Inv_Sku.isin(used)][['Inv_Sku','Inv_Desc']].to_string())
