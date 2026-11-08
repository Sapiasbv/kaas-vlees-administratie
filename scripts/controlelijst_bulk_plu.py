"""Controlelijst voor collega's: per bulk-item (RE-nummer + naam) de PLU's die eraan gekoppeld zijn.

Een tabblad per soort (Vlees, Kaas). Per bulk een regel, de PLU's ernaast (PLU + naam).
Kolommen 'Klopt?' en 'Opmerking' om in te vullen. Draaien: python scripts/controlelijst_bulk_plu.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from kva.bronnen import lees_re_export, lees_weegschaal  # noqa: E402
from kva.instellingen import laad_instellingen, laad_regels, uitvoermap, zoek_bestand  # noqa: E402
from kva.koppeling import koppel  # noqa: E402
from kva.mappingtabel import bulk_artikelnaam  # noqa: E402
from kva.opslag import vrije_naam  # noqa: E402

KOP = PatternFill("solid", fgColor="1F3864")
BULK = PatternFill("solid", fgColor="E1EEF9")
INVUL = PatternFill("solid", fgColor="FFF9DB")
DUN = Side(style="thin", color="B4C6E7")
RAND = Border(left=DUN, right=DUN, top=DUN, bottom=DUN)

regels, inst = laad_regels(), laad_instellingen()
re_pad, w_pad = zoek_bestand(inst["bronnen"]["re_export"]), zoek_bestand(inst["bronnen"]["weegschaal"])
re_df = lees_re_export(re_pad, regels)
weeg = lees_weegschaal(w_pad)

wb = Workbook()
wb.remove(wb.active)
tellingen = []
for soort in ("vlees", "kaas"):
    k = koppel(weeg, re_df, regels, soort)
    p = k.plus[k.plus.bulk_sku.ne("")]
    groepen = {sku: g.sort_values("PLU") for sku, g in p.groupby("bulk_sku")}
    bulks = k.bulks.set_index("Inv_Sku")
    volgorde = sorted(groepen, key=lambda s: bulk_artikelnaam(bulks.at[s, "Inv_Desc"]).lower())
    max_plu = max(len(g) for g in groepen.values())

    ws = wb.create_sheet(soort.capitalize())
    ws.append([f"Controle koppeling bulk → PLU ({soort}) — {datetime.now():%d-%m-%Y}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Klopt de koppeling? Vul per bulk 'ja' of 'nee' in en zet bij 'nee' in Opmerking wat er moet veranderen. "
               "Gecontroleerd door: ____________________"])
    ws.append([])
    kop = ["Nr", "Bulk RE-nummer", "Bulk naam", "Leverancier", "Aantal PLU's", "Klopt? (ja/nee)", "Opmerking"]
    for i in range(1, max_plu + 1):
        kop += [f"PLU {i}", f"Naam {i}"]
    ws.append(kop)
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = KOP
        c.alignment = Alignment(wrap_text=True, vertical="center")
    n_plu = 0
    for nr, sku in enumerate(volgorde, start=1):
        g = groepen[sku]
        b = bulks.loc[sku]
        rij = [nr, sku, b.Inv_Desc, b.Inv_VendorID, len(g), None, None]
        for r in g.itertuples(index=False):
            rij += [int(r.PLU), r.omschrijving]
        ws.append(rij)
        n_plu += len(g)
        rnr = ws.max_row
        for j, c in enumerate(ws[rnr], start=1):
            c.border = RAND
            c.alignment = Alignment(vertical="top", wrap_text=j in (3, 7) or (j > 7 and j % 2 == 1))
        for j in (2, 3):
            ws.cell(rnr, j).fill = BULK
        ws.cell(rnr, 2).number_format = "@"
        ws.cell(rnr, 6).fill = INVUL
        ws.cell(rnr, 7).fill = INVUL
    for j, b in enumerate([5, 16, 38, 14, 8, 10, 30], start=1):
        ws.column_dimensions[get_column_letter(j)].width = b
    for i in range(max_plu):
        ws.column_dimensions[get_column_letter(8 + 2 * i)].width = 7
        ws.column_dimensions[get_column_letter(9 + 2 * i)].width = 30
    ws.freeze_panes = "D5"
    ws.print_title_rows = "4:4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.oddFooter.center.text = "Pagina &P van &N"
    tellingen.append((soort, len(volgorde), n_plu, k.gekoppeld, k.aantal))

info = wb.create_sheet("Info")
for t in [f"Bron: {re_pad.name} en {w_pad.name}",
          *[f"{s.capitalize()}: {b} bulks, {n} PLU's gekoppeld (van {a} PLU's in RE)" for s, b, n, g, a in tellingen],
          "Niet in deze lijst: genegeerde PLU's (o.a. patés, Pastrami, Rundervink, droge worst, bakkerij)."]:
    info.append([t])
info.column_dimensions["A"].width = 100

pad = vrije_naam(uitvoermap(inst) / f"Controle_bulk_PLU_{datetime.now():%Y_%m_%d}.xlsx")
wb.save(pad)
for s, b, n, g, a in tellingen:
    print(f"{s}: {b} bulks, {n} PLU's in lijst | koppeling: {g} van {a} gekoppeld")
print(f"-> {pad}")
