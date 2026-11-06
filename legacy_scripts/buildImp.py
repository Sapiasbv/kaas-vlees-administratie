import sys,openpyxl,datetime as dt
sys.path.insert(0,'/tmp/claude-0/c')
from imp_data import *
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter as L
U="/root/.claude/uploads/409f47d1-0774-59fa-8af2-ef9852bec079/"
wb=openpyxl.load_workbook(glob.glob(U+"*Template*")[0]); ws=wb.active; ws.title="Import"
hdr=[c.value for c in ws[1]]; notes=[c.value for c in ws[2]]
ws.delete_rows(2)
col={h:i+1 for i,h in enumerate(hdr)}
NAVY="1F3864"
# --- Parameters
pm=wb.create_sheet("Parameters")
pm["A1"]="Parameters voor kostprijs en verkoopprijs van nieuwe bulk-items"; pm["A1"].font=Font(bold=True,size=14,color=NAVY)
P=[("Landed-cost factor",1.5,"Alleen nog gebruikt voor bulk-items zonder RE-artikel met prijs (de 3 samengestelde). Kostprijs = laatste factuurprijs per kg x koers x deze factor."),
   ("Koers EUR naar USD",1.00,"Van Kooten factureert in EUR, DeliNova in USD. 1.00 = geen omrekening. Zet hier de koers neer als RE in USD rekent."),
   ("Verkoopprijs-factor",1.35,"Price1-5 = kostprijs x deze factor. Bestaande bulk-items in RE hebben 1.35 (sommige DeliNova-rundvlees 1.5). Bulk wordt niet verkocht; veld is wel verplicht.")]
for i,(a,b,c) in enumerate(P,2):
    pm.cell(i,1,a).font=Font(bold=True); x=pm.cell(i,2,b); x.fill=PatternFill("solid",fgColor="FFF8DC"); pm.cell(i,3,c).alignment=Alignment(wrap_text=True,vertical="top")
pm.column_dimensions["A"].width=26; pm.column_dimensions["B"].width=10; pm.column_dimensions["C"].width=110
# --- rows
imp=[]  # dict per import row
for r in allb: imp.append(dict(kind='bulk',**r))
for r in mis.itertuples():
    grp=r._4
    cls='0301: Vleeswaren vers gesneden' if grp=='Vleeswaren' else '0202: Rund'
    dept='03. Vleeswaren' if grp=='Vleeswaren' else '02. Slagerij vers'
    imp.append(dict(kind='plu',soort='PLU-artikel ontbreekt in RE',desc=clean(r.Artikel) if False else r.Artikel,lev=VEND.get(r.Leverancier,''),levw=r.Leverancier,best='',plus=[r.PLU],art=r.Artikel,dept=dept,cls=cls,lp=None,retailRE=0,sku=str(200000+r.PLU)))
# --- Koppeling sheet
ks=wb.create_sheet("Koppeling")
ks["A1"]="Koppeling bulk-item en weegschaal-PLU's (niet importeren)"; ks["A1"].font=Font(bold=True,size=14,color=NAVY)
ks["A2"]="Rij = rijnummer op tabblad Import. Hier staat welke weegschaal-PLU's (RE-artikel = PLU + 200000) aan welk nieuw bulk-item hangen."; ks["A2"].font=Font(italic=True,color="555555")
kh=["Rij op Import","Soort","Bulk-/artikelnaam","Leverancier (weegschaal)","Bestelnr leverancier","Weegschaal-PLU's","RE-artikelnrs (PLU+200000)","Weegschaal-artikel(en)","Retail-artikel al in RE (aantal)","Laatste factuurprijs per kg","Valuta","Opmerking"]
hf=Font(bold=True,color="FFFFFF"); hfill=PatternFill("solid",fgColor=NAVY); thin=Side(style="thin",color="D0D5DD"); bd=Border(left=thin,right=thin,top=thin,bottom=thin)
for j,(h,wd) in enumerate(zip(kh,[9,34,52,22,22,22,28,60,14,14,8,60]),1):
    c=ks.cell(4,j,h); c.fill=hfill; c.font=hf; c.alignment=Alignment(wrap_text=True,vertical="center",horizontal="center"); ks.column_dimensions[L(j)].width=wd
ks.row_dimensions[4].height=44
RED=PatternFill("solid",bgColor="F4B6B6",fgColor="F4B6B6")
for n,x in enumerate(imp):
    ir=n+2; kr=n+5   # import row, koppeling row
    sku=x.get('sku')
    # import row
    vals={'Inv_Sku':sku,'Inv_Desc':x['desc'],'Inv_Loc_Taxable':False,'Inv_VendorID':x['lev'] or None,'Inv_DepartID':x['dept'],'Inv_ClassID':x['cls'],'Inv_Part_Vendor':x['best'] or None}
    for k,v_ in vals.items(): ws.cell(ir,col[k],v_)
    if x['kind']=='bulk' and x['rp']:
        keys=['Inv_Cost_Last','Inv_Loc_Price_Was','Inv_Loc_Price1','Inv_Loc_Price2','Inv_Loc_Price3','Inv_Loc_Price4','Inv_Loc_Price5']
        for k,vv in zip(keys,x['rp']['vals']): ws.cell(ir,col[k],vv)
    elif x['kind']=='bulk':
        ws.cell(ir,col['Inv_Cost_Last'],f'=IF(Koppeling!J{kr}="",0,ROUND(Koppeling!J{kr}*IF(Koppeling!K{kr}="EUR",Parameters!$B$3,1)*Parameters!$B$2,2))')
        for k in ['Inv_Loc_Price_Was','Inv_Loc_Price1','Inv_Loc_Price2','Inv_Loc_Price3','Inv_Loc_Price4','Inv_Loc_Price5']:
            ws.cell(ir,col[k],f'=ROUND($C{ir}*Parameters!$B$4,3)')
    ws.cell(ir,col['Inv_Loc_Taxable']).value=False
    # koppeling row
    opm=[]
    if x['kind']=='bulk':
        if x['soort'].startswith('B'): opm.append("Bestelnr leverancier ontbreekt: vul Inv_Part_Vendor in op Import")
        if x['soort'].startswith('C'): opm.append("Samengesteld/eigen productie: controleer of hier een bulk-item voor nodig is")
        if x['rp']: opm.append("Kost- en verkoopprijs overgenomen van RE-artikel %s (PLU %d)"%(x['rp']['sku'],x['rp']['plu']))
        else: opm.append("Geen RE-artikel met prijs gevonden: kostprijs staat op 0")
        if x['rp'] and x['rp']['diff']: opm.append("Let op: de PLU's onder dit bulk-item hebben verschillende prijzen; prijs van hoofd-PLU gebruikt")
        if x['best'] in ('93',) : opm.append("Let op: PLU 3025 (Prosciutto) en 3063 (Iberico) hebben bestelnr 93 = runderrookvlees; waarschijnlijk fout in weegschaal-lijst")
    else:
        opm.append("Retail-artikel: SKU = PLU + 200000. Verkoopprijs en kostprijs nog invullen")
        if not x['lev']: opm.append("Leverancier onbekend")
    row=[ir,x['soort'],x['desc'],x['levw'],x['best'] or None,", ".join(map(str,x['plus'])),", ".join(str(200000+p) for p in x['plus']),x['art'],x['retailRE'],x['lp'][0] if x['lp'] else None,x['lp'][1] if x['lp'] else None,"; ".join(opm)]
    for j,v_ in enumerate(row,1):
        c=ks.cell(kr,j,v_); c.border=bd; c.alignment=Alignment(vertical="top",wrap_text=j in (3,8,12))
n=len(imp); last=n+1
# --- styling Import
ws.freeze_panes="C2"
for j,h in enumerate(hdr,1):
    ws.column_dimensions[L(j)].width=max(ws.column_dimensions[L(j)].width or 10,14)
ws.column_dimensions["A"].width=16; ws.column_dimensions["B"].width=60; ws.column_dimensions["K"].width=18; ws.column_dimensions["L"].width=20; ws.column_dimensions["M"].width=30; ws.column_dimensions["O"].width=24
for r in range(2,last+1):
    for k in ['Inv_Cost_Last','Inv_Loc_Price_Was','Inv_Loc_Price1','Inv_Loc_Price2','Inv_Loc_Price3','Inv_Loc_Price4','Inv_Loc_Price5']: ws.cell(r,col[k]).number_format='0.00##'
ws.conditional_formatting.add(f"A2:L{last}",FormulaRule(formula=['A2=""'],fill=RED))
ws.conditional_formatting.add(f"C2:I{last}",FormulaRule(formula=['AND(C2<>"",C2=0)'],fill=RED))
ws.auto_filter.ref=f"A1:AQ{last}"
# --- Toelichting
tl=wb.create_sheet("Template-uitleg"); tl["A1"]="Veldomschrijving uit het RetailEdge-template (rode kolomkoppen = verplicht)"; tl["A1"].font=Font(bold=True,size=14,color=NAVY)
tl.cell(3,1,"Veld").font=Font(bold=True); tl.cell(3,2,"Verplicht").font=Font(bold=True); tl.cell(3,3,"Uitleg").font=Font(bold=True)
for i,(h,nt) in enumerate(zip(hdr,notes),4):
    tl.cell(i,1,h); tl.cell(i,2,"Ja" if i-4<12 else "Nee"); c=tl.cell(i,3,nt); c.alignment=Alignment(wrap_text=True,vertical="top")
tl.column_dimensions["A"].width=24; tl.column_dimensions["B"].width=10; tl.column_dimensions["C"].width=110
# --- Controle
ct=wb.create_sheet("Controle",0)
ct["A1"]="Importbestand RetailEdge - nieuwe bulk-items en ontbrekende PLU-artikelen"; ct["A1"].font=Font(bold=True,size=15,color=NAVY)
ct["A2"]="Rode cellen op tabblad Import = nog in te vullen. Sla tabblad Import op als CSV zodra alles gevuld is."; ct["A2"].font=Font(italic=True,color="555555")
nb_=sum(1 for x in imp if x['kind']=='bulk'); npl=n-nb_
rowsC=[("Aantal regels op Import",f"=COUNTA(Import!B2:B{last})","waarvan %d bulk-items en %d ontbrekende PLU-artikelen"%(nb_,npl)),
("Regels zonder Inv_Sku",f'=COUNTBLANK(Import!A2:A{last})',"Bulk-SKU's geef jij zelf (RE-nummering). Retail-artikelen hebben SKU = PLU + 200000."),
("Regels met kostprijs 0 of leeg",f'=COUNTBLANK(Import!C2:C{last})+COUNTIF(Import!C2:C{last},0)',"Bulk-items zonder RE-artikel met prijs (3 samengestelde) en de 5 nieuwe PLU-artikelen."),
("Regels zonder verkoopprijs (Price1)",f'=COUNTBLANK(Import!E2:E{last})+COUNTIF(Import!E2:E{last},0)',"De 5 nieuwe PLU-artikelen en 3 samengestelde bulk-items hebben geen bron."),
("Regels zonder Inv_VendorID",f'=COUNTBLANK(Import!K2:K{last})',"PLU 3217 heeft geen leverancier in de weegschaal-lijst."),
("Regels zonder Inv_Part_Vendor",f'=COUNTBLANK(Import!O2:O{last})',"Bestelnummer leverancier ontbreekt voor groep B en C en de 5 retail-artikelen."),]
for j,h in enumerate(["Controle","Aantal","Toelichting"],1):
    c=ct.cell(4,j,h); c.fill=hfill; c.font=hf
for i,(a,f,b) in enumerate(rowsC,5):
    ct.cell(i,1,a); ct.cell(i,2,f); ct.cell(i,3,b)
ct.cell(12,1,"Aannames (controleer)").font=Font(bold=True,size=12,color=NAVY)
AS=["Naam = 'Bulk <leveranciersnr>, <omschrijving>', zoals bij de bestaande bulk-items. Omschrijving uit de oude lijst, anders van de factuur, anders uit de weegschaal-lijst.",
"1 bulk-item per leveranciersnummer, ook als meerdere PLU's eraan hangen (bijv. 5272 Kippenvleugels voor 4 PLU's). Bij groep B en C (geen bestelnr of samengesteld) is het 1 bulk per PLU.",
"Vendor volgens RE-schrijfwijze: Van Kooten=VAN KOOTEN, Deli Nova=DELI NOVA, Deelen ZV=DEELEN, Deelen LV=DEELEN - LV. Bij een bulk met meerdere weegschaal-leveranciers is 'One time' genegeerd.",
"Afdeling/klasse volgt de bestaande retail-artikelen in RE; bulk met vleeswaren komt in '03. Vleeswaren', de rest in '02. Slagerij vers'.",
"Kost- en verkoopprijzen (Price_Was t/m Price5) van bulk-items zijn overgenomen van het bijbehorende RE-artikel (PLU + 200000, locatie Main). Hangen er meerdere PLU's aan, dan is de laagste PLU (niet 'One time') gebruikt; zie Koppeling. Het verschil met de laatste factuurprijs staat in kolom J.",
"Ham di Pasku (PLU 3090/3091) bestaat al in RE als bulk-item (2024700084939 en 2024700084946) en staat niet in dit bestand. Taxable staat overal op FALSE, zoals bij de bestaande bulk-items.",
"Weegschaal-PLU 3025 (Prosciutto) en 3063 (Iberico) hebben bestelnr 93 (runderrookvlees); waarschijnlijk een fout in de weegschaal-lijst. Ze hangen nu aan Bulk 93."]
for i,t in enumerate(AS,13):
    c=ct.cell(i,1,t); c.alignment=Alignment(wrap_text=True,vertical="top"); ct.merge_cells(start_row=i,start_column=1,end_row=i,end_column=3); ct.row_dimensions[i].height=34
ct.column_dimensions["A"].width=42; ct.column_dimensions["B"].width=10; ct.column_dimensions["C"].width=100
wb._sheets=[wb["Controle"],wb["Import"],wb["Koppeling"],wb["Parameters"],wb["Template-uitleg"]]; wb.active=1
OUT="/mnt/user-data/outputs/RetailEdge_Import_Bulk_en_PLU_2026_11_04.xlsx"; wb.save(OUT); print("saved",nb_,npl)
