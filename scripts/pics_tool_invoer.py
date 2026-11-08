"""Invoerlijst voor het tabblad Vlees (en Kaas) van het PICS-tool van Nick (Genereer_PICS_import.xlsm).

Het .xlsm-bestand zelf wordt NIET aangepast (macro's). Dit script maakt een los Excel-bestand met
precies de kolommen A t/m I van het tool, om te plakken als waarden. Draaien:
    python scripts/pics_tool_invoer.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from kva.bronnen import lees_mappingtabel, lees_re_export, lees_weegschaal  # noqa: E402
from kva.instellingen import laad_instellingen, laad_regels, uitvoermap, zoek_bestand  # noqa: E402
from kva.koppeling import koppel  # noqa: E402
from kva.mappingtabel import KOLOMMEN, maak_mappingtabel, verschil_met_tool  # noqa: E402
from kva.opslag import vrije_naam  # noqa: E402

KOP = PatternFill("solid", fgColor="1F3864")
GEEL = PatternFill("solid", fgColor="FFF2CC")

regels, inst = laad_regels(), laad_instellingen()
paden = {k: zoek_bestand(inst["bronnen"][k]) for k in ("re_export", "weegschaal", "pics_tool")}
re_df = lees_re_export(paden["re_export"], regels)
weeg = lees_weegschaal(paden["weegschaal"])
tool = lees_mappingtabel(paden["pics_tool"], regels.pics_menu_tabblad)

wb = Workbook()
uitleg = wb.active
uitleg.title = "Uitleg"
tellingen = []
for soort, tab in (("vlees", "Vlees"), ("kaas", "Kaas")):
    k = koppel(weeg, re_df, regels, soort)
    tabel = maak_mappingtabel(k, regels)
    ws = wb.create_sheet(f"Invoer {tab}")
    ws.append(KOLOMMEN)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = KOP
    for r in tabel.itertuples(index=False):
        ws.append(list(r))
        if r[8]:
            ws.cell(ws.max_row, 9).fill = GEEL
    for j, b in enumerate([14, 16, 14, 40, 16, 10, 12, 42, 60], 1):
        ws.column_dimensions[get_column_letter(j)].width = b
    ws.freeze_panes = "A2"
    v = verschil_met_tool(tabel, tool, tab)
    v.insert(0, "Tabblad", tab)
    tellingen.append((tab, len(tabel), int(k.gekoppeld), int(k.aantal), v))

wijz = wb.create_sheet("Wijzigingen t.o.v. tool")
alle = pd.concat([t[4] for t in tellingen], ignore_index=True)
wijz.append(list(alle.columns))
for c in wijz[1]:
    c.font = Font(bold=True)
for r in alle.itertuples(index=False):
    wijz.append([None if (isinstance(x, float) and pd.isna(x)) else x for x in r])
for j, b in enumerate([10, 12, 42, 18, 18, 60], 1):
    wijz.column_dimensions[get_column_letter(j)].width = b

regels_uitleg = [
    ("Invoer voor het PICS-tool (Genereer_PICS_import.xlsm)", True),
    (f"Gemaakt {datetime.now():%d-%m-%Y %H:%M} uit {paden['re_export'].name} en {paden['weegschaal'].name}.", False),
    ("", False),
    *[(f"Tabblad 'Invoer {t}': {n} regels, {g} van {a} PLU's gekoppeld aan een bulk. Wijzigingen: {len(v)}.", False)
      for t, n, g, a, v in tellingen],
    ("", False),
    ("Zo zet je het in het tool:", True),
    ("1. Maak eerst een kopie van Genereer_PICS_import.xlsm (reservekopie).", False),
    ("2. Open het tool in Excel en ga naar tabblad Vlees.", False),
    ("3. Selecteer A2:I500 en druk op Delete (alleen inhoud wissen, geen rijen verwijderen). Kolom J (Validatie) blijft staan.", False),
    ("4. Ga in dit bestand naar 'Invoer Vlees', selecteer A2 t/m de laatste regel in kolom I en kopieer (Ctrl+C).", False),
    ("5. Klik in het tool op Vlees!A2 en kies Plakken speciaal > Waarden (Ctrl+Alt+V, W, Enter).", False),
    ("6. Controleer rechtsboven (L1/M1): 'OK - mapping compleet'. Kolom J moet overal leeg zijn.", False),
    ("7. Herhaal 2-6 voor tabblad Kaas met 'Invoer Kaas' (alleen als kaas ook via het tool gaat).", False),
    ("8. Opslaan als .xlsm (Excel-werkmap met macro's).", False),
    ("", False),
    ("Let op:", True),
    ("- Gele cellen in kolom 'Let op': lees de opmerking. Rolladeschijf (3050) wordt per stuk verkocht; het tool boekt", False),
    ("  het aantal stuks als kg af van bulk Buik. Corrigeer die bulkregel met de hand (aantal x 0,150 kg).", False),
    ("- Samengestelde artikelen (3101, 3612, 3615, 3691) staan op één bulk; dat is een bewuste keuze.", False),
    ("- Tabblad 'Wijzigingen t.o.v. tool' laat zien wat er verandert ten opzichte van het huidige tool.", False),
    ("- Gebruik voor dezelfde week niet ook de nieuwe app: dan wordt alles dubbel geboekt.", False),
]
for i, (t, vet) in enumerate(regels_uitleg, 1):
    uitleg.cell(i, 1, t).font = Font(bold=vet, size=13 if i == 1 else 11)
uitleg.column_dimensions["A"].width = 130

pad = vrije_naam(uitvoermap(inst) / f"PICS_tool_invoer_{datetime.now():%Y_%m_%d}.xlsx")
wb.save(pad)
for t, n, g, a, v in tellingen:
    print(f"{t}: {n} regels | gekoppeld {g}/{a} | wijzigingen {len(v)}: {v.Wijziging.value_counts().to_dict()}")
print(f"-> {pad}")
