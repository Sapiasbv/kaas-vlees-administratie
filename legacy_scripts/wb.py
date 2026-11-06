import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
exec(open('/tmp/claude-0/d/link.py').read())
m=pd.read_pickle('m.pkl'); bp=pd.read_pickle('bp.pkl')
wb=Workbook()
H=PatternFill('solid',fgColor='1F3864'); HF=Font(bold=True,color='FFFFFF')
RED=PatternFill('solid',fgColor='F8CBAD'); GRN=PatternFill('solid',fgColor='E2EFDA'); YEL=PatternFill('solid',fgColor='FFF2CC')
def sheet(ws,cols,rows,widths,fillcol=None,fillmap=None):
    ws.append(cols)
    for c in ws[1]: c.fill=H; c.font=HF; c.alignment=Alignment(wrap_text=True,vertical='top')
    for r in rows: ws.append(r)
    for i,wd in enumerate(widths,1): ws.column_dimensions[get_column_letter(i)].width=wd
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    if fillcol is not None:
        for row in ws.iter_rows(min_row=2):
            f=fillmap(row[fillcol].value)
            if f: row[fillcol].fill=f
def clean(n): return re.sub(r',?\s*p/(kg|st)\.?','',str(n)).strip()
# 1 PLU -> Bulk
ws=wb.active; ws.title='PLU naar Bulk'
rows=[]
for r in m.itertuples():
    rows.append([r.PLU,r.sku,clean(r.Artikel),r.Lev,r.Best,r.re_Inv_VendorID,r.repv,r.bulk,bi.loc[r.bulk,'Inv_Desc'] if r.bulk else '',bi.loc[r.bulk,'Inv_VendorID'] if r.bulk else '',bi.loc[r.bulk,'pv'] if r.bulk else '',r.status,r.reden if isinstance(r.reden,str) else ''])
sheet(ws,['PLU','RE art. nr','Artikel','Leverancier (weegschaal)','Bestelnr (weegschaal)','Vendor (RE)','Vendor part nr (RE)','Bulk SKU','Bulk naam','Bulk vendor','Bulk part nr','Status','Opmerking'],rows,[8,10,34,16,18,16,38,16,38,14,16,20,60],11,lambda v: GRN if v=='Gekoppeld' else (YEL if v and 'tekst' in v else RED))
# 2 Bulk -> PLU
ws=wb.create_sheet('Bulk naar PLU')
rows=[[r.sku,r.naam,r.vendor,r.pv,r.n,r.plus,r.art,'OK' if r.n else 'GEEN PLU gekoppeld'] for r in bp.itertuples()]
sheet(ws,['Bulk SKU','Bulk naam','Vendor','Part nr','Aantal PLU','PLU nummers','Artikelen','Status'],rows,[16,48,16,22,10,28,90,20],7,lambda v: GRN if v=='OK' else RED)
# 3 Acties
A=[]
def a(prio,wat,waar,item,nu,nieuw,toel=''): A.append([len(A)+1,prio,wat,waar,item,nu,nieuw,toel])
# A. koppeling herstellen
a(1,'Part nr corrigeren','RE bulk','2024700092798 Bulk 210405, Striploin','21405','210405','Typfout. Daarna hangen PLU 3606 en 3607 eraan.')
a(1,'Part nr aanvullen','RE retail','203600 Flanksteak','", Flanksteak p/kg"','210403, Flanksteak','Bulk 2024700105696 heeft part nr 210403.')
a(1,'Part nr aanvullen','RE retail','203647 Gehaktbal Vers','", MAG MET varkens dv"','3, MAG MET varkens dv','Bulk 2024700092712 heeft part nr 3.')
a(1,'Part nr gelijk maken','RE retail','203643 Slavink vers','", varkens trimmings/snippers"','varkens trimmings/snipper','Moet exact gelijk zijn aan het bulk part nr (bulk 2024700106211).')
for p in (3641,3651,3652): a(1,'Part nr aanvullen','RE retail',f'20{p} {clean(m[m.PLU==p].Artikel.iloc[0])}','Rundersnippers 80/20 Kooten','210190, Rundersnippers 80/20 Kooten','Bulk 2024700092620 heeft part nr 210190.')
sp={5802:'Garnalenspies',5814:'Noorse Zalmspies groene paprika',4610:'Kipshaslick',4300:'Hawaispies',4400:'Globespies',7900:'Varkens Shaslick'}
bsk={5802:'2024700106433',5814:'2024700106440',4610:'2024700106426',4300:'2024700106402',4400:'2024700106419',7900:'2024700106457'}
for p,n in sp.items():
    a(1,'Part nr op bulk invullen','RE bulk',f'{bsk[p]} Bulk, {n}','(leeg)',m[m.PLU==p].repv.iloc[0],f'Zelfde nummer als retail {200000+p}.')
a(1,'Part nr op bulk invullen','RE bulk','2024700106495 Bulk, BBQ Pakket 2 personen diepvries','(leeg)','203691','Zelfde nummer als retail 203691.')
a(1,'Part nr op bulk invullen','RE bulk','2024700106228 Bulk, Turkeyham Carolina','(leeg)','40013501','Zelfde nummer als retail 203002. Vendor retail 203002 staat op Eigen Slagerij, moet DEELEN zijn.')
a(1,'Vendor corrigeren','RE retail','203002 Turkeyham Carolina','Eigen Slagerij','DEELEN','Weegschaal: Deelen ZV.')
# B. leeg/leeg
leeg=m[(m.status=='NIET gekoppeld')&m.reden.str.startswith('Retail part nr leeg')]
for r in leeg.itertuples():
    a(2,'Part nr invullen op retail en bulk','RE retail + bulk',f'{r.sku} {clean(r.Artikel)}','(leeg)','Leverancierscode, of anders RE art. nr '+r.sku,'Bulk: '+', '.join(sorted(bulk[bulk.Inv_Desc.str.contains(re.escape(clean(r.Artikel).split()[0]),case=False)&(bulk.pv=='')].Inv_Sku))[:60] if False else f'Bulk: zie Bulk naar PLU (zonder part nr). Waarde op retail en bulk identiek maken.')
for p in (3101,3612,3615,3691):
    r=m[m.PLU==p].iloc[0]
    a(2,'Vendor gelijktrekken','RE retail',f'{r.sku} {clean(r.Artikel)}',r.re_Inv_VendorID,'EIGEN PRODUCTIE','Weegschaal: Eigen productie; bulk staat op EIGEN PRODUCTIE.')
for p in (3562,3563,3564):
    r=m[m.PLU==p].iloc[0]
    a(2,'Vendor corrigeren','RE retail',f'{r.sku} {clean(r.Artikel)}',r.re_Inv_VendorID,'FOODS USA','Weegschaal: Foods USA; bulk staat op FOODS USA.')
# C. beslissingen
a(3,'Beslissen: welk nummer klopt?','RE / bulk / weegschaal','PLU 3020 Katenspek','RE retail: 2114. Bulk 2024700105993 en weegschaal: 3020','2114 of 3020','3020 is gelijk aan het PLU nummer, dus waarschijnlijk geen leveranciersnummer. Controleer op factuur/prijslijst Van Kooten.')
a(3,'Beslissen: welk nummer klopt?','weegschaal / RE','PLU 3508 Kipshoarma','Weegschaal 310007, RE 310006 (bulk Kippenborst)','310006 of 310007','Er is geen bulk 310007.')
a(3,'Beslissen','RE retail / weegschaal','PLU 3050 Rolladeschijf','RE part nr leeg, weegschaal 2098 (Buik)','2098, Buik z/b z/zw z/kn varkens (als juist)','Vendor staat op ONE TIME terwijl bulk 2098 van VAN KOOTEN is.')
a(3,'Weegschaal corrigeren','Weegschaal','PLU 3025 Prosciutto Crudo','Bestelnr 93 (runderrookvlees)','1024000 (zoals RE) of leeg','Er is geen bulk-item. Maak er een als je deze structureel inkoopt, anders blijft het One time.')
a(3,'Weegschaal corrigeren','Weegschaal','PLU 3063 Iberico diepvries','Bestelnr 93, vendor One time','2307','RE hangt al aan Bulk 2307 (Van Kooten). RE retail vendor staat op ONE TIME.')
a(3,'Weegschaal corrigeren','Weegschaal','PLU 3641, 3651, 3652, 3682','Leverancier Deelen ZV','Van Kooten','RE en bulk 210190 staan op VAN KOOTEN.')
# D. ontbrekend
a(2,'Aanmaken in RE','RE','PLU 3120 Lamsbout zonder been diepvries (Van Kooten)','Niet in RE','Retail 203120 + bulk','Nieuw in weegschaal; geen bestelnr bekend.')
a(2,'Beslissen / aanmaken','RE','PLU 3026 Iberico diepvries','Niet in RE, geen leverancier','Aanmaken of uit weegschaal','Lijkt dubbel met PLU 3063.')
a(2,'Aanmaken in RE','RE','PLU 3217 Kalfs hart zwezerik','Niet in RE, geen leverancier','Retail 203217 + bulk','Leverancier en bestelnr nodig.')
a(2,'Beslissen','RE','PLU 3090 en 3091 Ham di Pasku','Alleen als 2024700084939 / 2024700084946 (HHB, geen part nr)','Retail 203090/203091 aanmaken, of bestaande items als PLU gebruiken','Part nr is leeg, dus geen koppeling mogelijk.')
a(3,'Beslissen','RE','PLU 2135 t/m 2138 Droge Worst (Deelen LV)','Bestaan als 2024700003534 t/m 2024700003565 met part nr 1002135 t/m 1002138','Zo laten of PLU-artikel 2xxxxx aanmaken','Scan-items, geen bulk nodig.')
a(3,'Opschonen weegschaal','Weegschaal','PLU 9999 test item, 999999 Plus handingave','Niet in RE','Verwijderen indien niet meer nodig','')
# E. klassen
a(4,'Klasse gelijktrekken','RE bulk','2024700092651 Bulk 2233 en 2024700092668 Bulk 202 (grillworst)','0405: Kaas Vleeswaren VVP','0203: Varkensvlees','Retail 3064/3067/3068/3111 staan op 0203.')
a(4,'Klasse gelijktrekken','RE bulk','2024700106112 Bulk 5476 Kiphamburgers','0203: Varkensvlees','0201: Kip','')
a(4,'Klasse controleren','RE retail/bulk','203716 Gehakt cordon bleu (bulk 5180), 203724 nasi bami (bulk 310006), 203645 Gehakt Halfom (bulk 3), 203004 Filet Americain (bulk 210406)','Retail en bulk klasse verschillen','Zelfde klasse kiezen','Bijv. 203716 retail Varkens, bulk Kip.')
ws=wb.create_sheet('Acties')
sheet(ws,['Nr','Prio','Actie','Waar','Item','Nu','Nieuw / gewenst','Toelichting'],A,[5,6,30,18,50,45,45,70])
for row in ws.iter_rows(min_row=2):
    for c in row: c.alignment=Alignment(wrap_text=True,vertical='top')
# samenvatting
ns=len(m); g=(m.status!='NIET gekoppeld').sum()
S=wb.create_sheet('Samenvatting',0)
vals=[('Controle RE-export 04-11-2026 en weegschaal-lijst 04-11-2026',''),('',''),
('Vlees/vleeswaren PLU-artikelen in RE (excl. salades/fruit/DIFS/kaas)',ns),
('  Gekoppeld aan een bulk-item (via vendor part nr)',int(g)),
('  Niet gekoppeld',int(ns-g)),
('Bulk-items vlees in RE',len(bp)),
('  Met minstens 1 PLU',int((bp.n>0).sum())),
('  Zonder PLU (nog geen koppeling)',int((bp.n==0).sum())),
('Weegschaal-PLU niet in RE (vlees): 2135-2138, 3026, 3090, 3091, 3120, 3217',9),
('Overige items in RE (dept 02/03) buiten de weegschaal-lijst',0),
('Aantal acties (zie tabblad Acties)',len(A)),
('',''),('Uitleg',''),
('Koppeling = vendor part nr van het retail-item begint met het part nr van het bulk-item (bijv. "2145, Serranoham blok varkens" hoort bij Bulk 2145). Bij bulk-items zonder nummer gaat dat op tekst.',''),
('Kleur: groen = gekoppeld, geel = gekoppeld op tekst, rood = niet gekoppeld.',''),
('Kost- en verkoopprijzen in RE zijn gelijk aan de weegschaal-lijst voor alle vlees-PLU (geen verschillen).',''),
('Afdeling 14 Hardlopers / 13 Basismand op retail-items is genegeerd (bewust anders dan bulk).','')]
for v in vals: S.append(list(v))
S.column_dimensions['A'].width=110; S.column_dimensions['B'].width=10; S['A1'].font=Font(bold=True,size=13); S['A13'].font=Font(bold=True)
import os
p='/mnt/user-data/outputs/Vlees_koppeling_controle_2026_11_04.xlsx'
wb.save(p); print(p,len(A),ns,g,(bp.n==0).sum())
