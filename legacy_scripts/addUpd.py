import sys; sys.path.insert(0,'/tmp/claude-0/c')
from imp_data import *
import openpyxl
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter as L
OUT="/mnt/user-data/outputs/RetailEdge_Import_Bulk_en_PLU_2026_11_04.xlsx"
wb=openpyxl.load_workbook(OUT); imp=wb["Import"]; hdr=[c.value for c in imp[1]]
MAP={'User Field 4':'Text on Price Tag','CustomSubTotal1':'EBT','CustomSubTotal2':'DUFB'}
# candidates
cand=[]; avw=[]
for r in w.itertuples():
    s=str(200000+r.PLU)
    if s not in main.index: continue
    m=main.loc[s]; pv=m['Inv_Part_Vendor'] if pd.notna(m['Inv_Part_Vendor']) else ''
    b=r.best
    if not pv:
        new=b if (b and b.lower()!='samengesteld') else ''
        cand.append(dict(plu=r.PLU,sku=s,art=r.Artikel,levW=r.Leverancier,best=b,new=new,m=m))
    elif b and b.lower() not in pv.lower() and b.lower()!='samengesteld':
        avw.append(dict(plu=r.PLU,sku=s,art=r.Artikel,levW=r.Leverancier,best=b,pv=pv,m=m))
cand.sort(key=lambda x:(x['new']=='',x['plu']))
for n in ("Import bijwerken","Bijwerken - info"):
    if n in wb.sheetnames: del wb[n]
up=wb.create_sheet("Import bijwerken"); 
for j,h in enumerate(hdr,1):
    c=up.cell(1,j,h); c.font=Font(color=imp.cell(1,j).font.color.rgb if imp.cell(1,j).font.color is not None and imp.cell(1,j).font.color.type=='rgb' else None); 
    up.column_dimensions[L(j)].width=imp.column_dimensions[L(j)].width or 14
def val(m,h):
    k=MAP.get(h,h)
    if k not in m.index: return None
    v=m[k]
    if pd.isna(v): return None
    if h=='Inv_Loc_Taxable': return str(v).lower()=='true'
    if h in ('Inv_Loc_DenySales','Inv_Cost_Dynamic','CustomSubTotal1','CustomSubTotal2','CustomSubTotal3'): return str(v).lower()=='true'
    if h in ('Inv_Sku','Inv_ItemID','Inv_Part_Vendor','Inv_UPC1','Inv_UPC2','Inv_Desc'): return str(v)
    try:
        f=float(v); return f
    except: return str(v)
for i,x in enumerate(cand,2):
    for j,h in enumerate(hdr,1):
        v=val(x['m'],h)
        if h=='Inv_Sku': v=x['sku']
        if h=='Inv_Part_Vendor': v=x['new'] or None
        up.cell(i,j,v)
        if h in ('Inv_Cost_Last','Inv_Loc_Price_Was') or h.startswith('Inv_Loc_Price'): up.cell(i,j).number_format='0.00##'
last=len(cand)+1
RED=PatternFill("solid",bgColor="F4B6B6",fgColor="F4B6B6")
up.conditional_formatting.add(f"O2:O{last}",FormulaRule(formula=['O2=""'],fill=RED))
up.freeze_panes="C2"; up.column_dimensions["B"].width=40
# info sheet
inf=wb.create_sheet("Bijwerken - info")
NAVY="1F3864"; hf=Font(bold=True,color="FFFFFF"); hfill=PatternFill("solid",fgColor=NAVY)
inf["A1"]="Bijwerken van bestaande RE-artikelen: vendor part nummer"; inf["A1"].font=Font(bold=True,size=14,color=NAVY)
inf["A2"]="Tabblad 'Import bijwerken' bevat de bestaande RE-artikelen (sleutel Inv_Sku) zonder Inv_Part_Vendor, met alle huidige RE-gegevens erin overgenomen zodat niets wordt overschreven. Alleen Inv_Part_Vendor is nieuw."; inf["A2"].font=Font(italic=True,color="555555")
H=["Regel op Import bijwerken","RE-artikel","PLU","Artikel","Leverancier weegschaal","Leverancier RE","Nieuw vendor part nr","Bron / opmerking"]
for j,(h,wd) in enumerate(zip(H,[12,12,8,38,18,18,20,90]),1):
    c=inf.cell(4,j,h); c.fill=hfill; c.font=hf; c.alignment=Alignment(wrap_text=True,vertical="center"); inf.column_dimensions[L(j)].width=wd
inf.row_dimensions[4].height=32
for i,x in enumerate(cand,5):
    if x['new']:
        op="Overgenomen uit 'Bestelnummer leverancier' in weegschaal-lijst"
        if x['plu']==3050: op+=". Controleer: 2098 is Buik, het artikel heet Rolladeschijf"
        if x['levW']!=x['m']['Inv_VendorID'] and x['levW'].upper().replace(' ZV','')!=str(x['m']['Inv_VendorID']).upper(): op+=f". Leverancier verschilt: weegschaal {x['levW']}, RE {x['m']['Inv_VendorID']} (niet aangepast)"
    elif x['best'].lower()=='samengesteld': op="Samengesteld artikel: geen leveranciersnummer. Leeg laten of eigen code kiezen"
    else: op="Geen bestelnummer in weegschaal-lijst en niet in de oude lijst: invullen"
    if x['levW']!=x['m']['Inv_VendorID'] and not x['new'] and x['levW'].upper().replace(' ','')!=str(x['m']['Inv_VendorID']).upper().replace(' ',''): op+=f". Leverancier verschilt: weegschaal {x['levW']}, RE {x['m']['Inv_VendorID']}"
    for j,v in enumerate([i-3,x['sku'],x['plu'],x['art'],x['levW'],x['m']['Inv_VendorID'],x['new'] or None,op],1):
        c=inf.cell(i,j,v); c.alignment=Alignment(vertical="top",wrap_text=(j==8))
    # row number on Import bijwerken = i-3+1
    inf.cell(i,1,i-3+0)
r0=5+len(cand)+2
inf.cell(r0,1,"Afwijkend, NIET opgenomen in de import (vendor part nr in RE wijkt af van weegschaal-lijst)").font=Font(bold=True,size=12,color=NAVY)
for j,h in enumerate(["","RE-artikel","PLU","Artikel","Leverancier weegschaal","Leverancier RE","Nu in RE","Bestelnr weegschaal-lijst"],1):
    c=inf.cell(r0+1,j,h); c.fill=hfill; c.font=hf
for i,x in enumerate(avw,r0+2):
    for j,v in enumerate([None,x['sku'],x['plu'],x['art'],x['levW'],x['m']['Inv_VendorID'],x['pv'],x['best']],1): inf.cell(i,j,v)
# fix row numbers on info: Import bijwerken data starts row 2
for i in range(5,5+len(cand)): inf.cell(i,1,i-3)
# Controle additions
ct=wb["Controle"]
r=ct.max_row+2
ct.cell(r,1,"Bestaande RE-artikelen bijwerken").font=Font(bold=True,size=12,color=NAVY)
ct.cell(r+1,1,"Regels op 'Import bijwerken'"); ct.cell(r+1,2,f"=COUNTA('Import bijwerken'!A2:A{last})"); ct.cell(r+1,3,"RE-artikelen zonder vendor part nummer (Inv_Part_Vendor)")
ct.cell(r+2,1,"Daarvan nog zonder nieuw nummer"); ct.cell(r+2,2,f"=COUNTBLANK('Import bijwerken'!O2:O{last})"); ct.cell(r+2,3,"Geen nummer in weegschaal-lijst; zie tabblad 'Bijwerken - info'. Vul in of laat regel weg uit de import.")
wb._sheets=[wb[n] for n in ["Controle","Import","Import bijwerken","Koppeling","Bijwerken - info","Parameters","Template-uitleg"]]
wb.save(OUT); print(len(cand),sum(1 for x in cand if x['new']),len(avw))
