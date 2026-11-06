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
fp=lambda sku: str(idx.loc[sku,'Inv_Part_Vendor'])
nb={'2024700105993':('2114','Bulk 2114, Katenspek varkens'),'2024700106273':('393','Bulk 393, Kalkoen salami'),'2024700106259':('5034','Bulk 5034, Kalkoenfilet gebraden'),
 '2024700106181':('2966','Bulk 2966, Kip grillworst naturel'),'2024700106204':('3010','Bulk 3010, Kalfsschenkel gezaagd'),'2024700106242':('111','Bulk 111, Berliner met spekrand'),
 '2024700106198':('2210','Bulk 2210, Rib karbonade gezaagd')}
for sk,(n,d) in nb.items():
    setc(sk,'Inv_Part_Vendor',n,'Nummer volgens pakbon Van Kooten 26766731'); setc(sk,'Inv_Desc',d,'Naam volgens "Bulk <nr>, <omschrijving>"')
for sk,pv in {'203040':'393, Kalkoen salami','203038':'5034, Kalkoenfilet gebraden','203070':'2966, Kip grillworst naturel','203699':'3010, Kalfsschenkel gezaagd','203036':'111, Berliner met spekrand','203041':'354, Kipcervelaatworst'}.items():
    setc(sk,'Inv_Part_Vendor',pv,'Nummer volgens pakbon Van Kooten 26766731')
for sk,bsk in {'203101':'2024700106464','203612':'2024700106471','203615':'2024700106488'}.items():
    setc(sk,'Inv_Part_Vendor',sk,'Eigen productie: RE artikelnummer als part nr'); setc(bsk,'Inv_Part_Vendor',sk,'Eigen productie: RE artikelnummer als part nr')
setc('203561','Inv_Part_Vendor',fp('203561').replace('KOCH2200','PER53284'),'Foods USA nieuw nummer PER53284 (was KOCH2200)')
setc('2024700105726','Inv_Part_Vendor','PER53284','Foods USA nieuw nummer PER53284 (was KOCH2200)')
setc('2024700105726','Inv_Desc',idx.loc['2024700105726','Inv_Desc'].replace('KOCH2200','PER53284'),'Nummer in naam aangepast')
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
o.append(['Item','Artikel','Opmerking'])
for c in o[1]: c.font=Font(bold=True)
for x in [('203508','Kipshoarma','Weegschaal 310007, RE 310006: welk nummer klopt?'),('203025','Prosciutto (One time)','Geen bulk-item'),('203050','Rolladeschijf (One time)','Part nr leeg'),
 ('203562-203564, 203043','Kippendij met bot (3x), Sausage links','Foods USA nummers onbekend (genegeerd)'),('203121-203126, 203027, 203644','Patés, Honingham, Pastrami, Rundervink','Tijdelijk/One time: genegeerd'),
 ('2024700106280','Bulk, Kip Cervelaat','Dubbel met Bulk 354 (Kipcervelaatworst). Kan uit RE verwijderd worden (voorraad 0).')]: o.append(list(x))
for j,wd in enumerate([28,42,70],1): o.column_dimensions[L(j)].width=wd
P='/mnt/user-data/outputs/RetailEdge_Import_Bijwerken_Koppeling_2026_11_05.xlsx'
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
m=pd.read_pickle('m.pkl'); mm=m.copy(); ok=0; bad=[]
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
