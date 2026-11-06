"""Bulks voor 3120, 3217, 3090 en 3091 toevoegen aan 'Import nieuw' van RetailEdge_Import_2026_11_06.xlsx.

Het bestand is al door Sjors ingevuld; dit script voegt alleen rijen toe en laat de rest staan.
Eerst gaat er een reservekopie naar uitvoer/_reserve/. Draaien: python scripts/re_import_2026_11_06_bulks.py

Inrichting volgens de 110 bestaande vlees-bulks in RE: SKU 2024700... (maakt Sjors zelf aan), naam
'Bulk <nr>, <omschrijving>' (zonder nummer: 'Bulk, <omschrijving>'), eenheid lb, afdeling en klasse
gelijk aan het retail-item, prijzen en kostprijs van het retail-item.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openpyxl import load_workbook  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402

PAD = Path(__file__).resolve().parents[1] / "uitvoer" / "RetailEdge_Import_2026_11_06.xlsx"
ROOD = PatternFill("solid", fgColor="F8CBAD")
VERPLICHT = ["Inv_Sku", "Inv_Desc", "Inv_Cost_Last", "Inv_Loc_Price1", "Inv_VendorID", "Inv_DepartID", "Inv_ClassID"]
PRIJZEN = ["Inv_Loc_Price_Was", "Inv_Loc_Price1", "Inv_Loc_Price2", "Inv_Loc_Price3", "Inv_Loc_Price4", "Inv_Loc_Price5"]

# retail-SKU -> (bulknaam, part nr bulk, reden, nog in te vullen)
BULKS = {
    "203120": ("Bulk, Lamsbout zonder been diepvries", None,
               "Bulk voor PLU 3120. Geen part nr bekend: koppelt op naam.",
               "Inv_Sku zelf aanmaken; part nr Van Kooten op retail en bulk zodra bekend"),
    "203217": ("Bulk, Kalfs hart zwezerik", None,
               "Bulk voor PLU 3217. Geen part nr bekend: koppelt op naam.",
               "Inv_Sku zelf aanmaken; part nr Van Kooten op retail en bulk zodra bekend"),
    "203090": ("Bulk H6159-0001, Ham di Pasku bone in", "H6159-0001",
               "Bulk voor PLU 3090 (HHB H6159-0001).", "Inv_Sku zelf aanmaken"),
    "203091": ("Bulk H6159-0005, Ham di Pasku boneless", "H6159-0005",
               "Bulk voor PLU 3091 (HHB H6159-0005).", "Inv_Sku zelf aanmaken"),
}

wb = load_workbook(PAD)
ws = wb["Import nieuw"]
koppen = [c.value for c in ws[1]]
kol = {k: i for i, k in enumerate(koppen)}
rijen = {str(r[kol["Inv_Sku"]]): r for r in ws.iter_rows(min_row=2, values_only=True) if r[kol["Inv_Sku"]]}
bestaand = {str(r[kol["Inv_Desc"]]) for r in ws.iter_rows(min_row=2, values_only=True)}
if any(naam in bestaand for naam, *_ in BULKS.values()):
    sys.exit("Bulks staan er al in; niets gedaan.")

reserve = PAD.parent / "_reserve" / f"{PAD.stem}_voor_bulks_{datetime.now():%H%M%S}.xlsx"
reserve.parent.mkdir(exist_ok=True)
shutil.copy2(PAD, reserve)

ov = wb["Overzicht"]
for retail, (naam, part, reden, open_punt) in BULKS.items():
    bron = dict(zip(koppen, rijen[retail]))
    v = {k: bron.get(k) for k in ["Inv_Cost_Last", *PRIJZEN, "Inv_VendorID", "Inv_DepartID", "Inv_ClassID",
                                  "Inv_Loc_Taxable", "Inv_DefaultQuantity", "Inv_Price_Min", "Inv_Cost_Dynamic",
                                  "Inv_Loc_DenySales", "CustomSubTotal1", "CustomSubTotal2", "CustomSubTotal3"]}
    v.update(Inv_Sku=None, Inv_Desc=naam, Inv_Part_Vendor=part, Inv_Weight_Unit="lb")
    ws.append([v.get(k) for k in koppen])
    r = ws.max_row
    for veld in VERPLICHT:
        if v.get(veld) in (None, ""):
            ws.cell(r, kol[veld] + 1).fill = ROOD
    ov.append(["Nieuw", "(SKU zelf aanmaken)", naam, "Nieuw bulk-item", reden, open_punt])

wb.save(PAD)
print(f"Reservekopie: {reserve}")
print(f"Toegevoegd: {len(BULKS)} bulks -> 'Import nieuw' heeft nu {ws.max_row - 1} regels")
