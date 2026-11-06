"""RE-import 6-11-2026: part nrs, klassen, Prosciutto-bulk en ontbrekende weegschaal-artikelen.

Beslissingen van Sjors (6-11-2026). Draaien: python scripts/re_import_2026_11_06.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kva.bronnen import lees_re_export  # noqa: E402
from kva.instellingen import laad_instellingen, laad_regels, uitvoermap, zoek_bestand  # noqa: E402
from kva.re_import import NieuwItem, Wijziging, schrijf, template_koppen  # noqa: E402

regels, inst = laad_regels(), laad_instellingen()
re_pad = zoek_bestand(inst["bronnen"]["re_export"])
re_df = lees_re_export(re_pad, regels)
template = zoek_bestand("data/templates/RetailEdge_CSV_Inventory_Import_Template*.xlsx")
koppen = template_koppen(template)

W = [
    # --- part nrs
    Wijziging("203126", {"Inv_Part_Vendor": "237, Gebraden honingham"}, "Honingham: Van Kooten 237 (Sjors)"),
    Wijziging("2024700106358", {"Inv_Part_Vendor": "237", "Inv_Desc": "Bulk 237, Gebraden honingham"},
              "Bulk honingham: nummer 237, naam volgens 'Bulk <nr>, <omschrijving>'"),
    Wijziging("203050", {"Inv_Part_Vendor": "2098, Rolladeschijf", "Inv_VendorID": "VAN KOOTEN",
                         "Inv_DepartID": "02. Slagerij vers", "Inv_ClassID": "0203: Varkensvlees"},
              "Rolladeschijf hoort bij bulk 2098 Buik (Sjors); leverancier en klasse gelijk aan de bulk"),
    # --- klassen (meest logische optie: volg de bulk, behalve waar de bulk zelf afwijkt)
    Wijziging("203004", {"Inv_ClassID": "0202: Rund"},
              "Filet americain uit bulk Paletta (Rund); de 3 andere PLU's op die bulk zijn ook 0202"),
    Wijziging("203304", {"Inv_ClassID": "0201: Kip"}, "Unique hamburger = Kiphamburgers gegaard (bulk 0201 Kip)"),
    Wijziging("203724", {"Inv_ClassID": "0201: Kip"}, "Nasi/bami vlees uit bulk Kippenborst (0201 Kip, 12 kip-PLU's)"),
    Wijziging("203645", {"Inv_ClassID": "0203: Varkensvlees"}, "Gehakt halfom uit bulk MAG MET varkens (0203)"),
    Wijziging("203647", {"Inv_ClassID": "0203: Varkensvlees"}, "Gehaktbal uit bulk MAG MET varkens (0203)"),
]


def kopie_retail(sku: str, **velden) -> dict:
    """Prijsvelden en vaste velden overnemen van het retail-item (zoals bij de eerdere bulk-import)."""
    r = re_df.loc[sku]
    v = {k: r[k] for k in ["Inv_Cost_Last", "Inv_Loc_Price_Was", "Inv_Loc_Price1", "Inv_Loc_Price2",
                          "Inv_Loc_Price3", "Inv_Loc_Price4", "Inv_Loc_Price5", "Inv_Weight_Unit"]}
    v.update(Inv_Loc_Taxable=False, Inv_DefaultQuantity=1, Inv_Price_Min=0, Inv_Cost_Dynamic=False,
             Inv_Loc_DenySales=False, CustomSubTotal1=False, CustomSubTotal2=False, CustomSubTotal3=False)
    v.update(velden)
    return v


def nieuw_retail(plu, desc, kost, prijs, vendor, dept, klasse, part=None):
    v = {"Inv_Sku": str(200000 + plu), "Inv_Desc": desc, "Inv_Cost_Last": kost, "Inv_VendorID": vendor,
         "Inv_DepartID": dept, "Inv_ClassID": klasse, "Inv_Part_Vendor": part, "Inv_Weight_Unit": "kg",
         "Inv_Loc_Taxable": False, "Inv_DefaultQuantity": 1, "Inv_Price_Min": 0, "Inv_Cost_Dynamic": False,
         "Inv_Loc_DenySales": False, "CustomSubTotal1": False, "CustomSubTotal2": False, "CustomSubTotal3": False}
    for k in ["Inv_Loc_Price_Was", "Inv_Loc_Price1", "Inv_Loc_Price2", "Inv_Loc_Price3", "Inv_Loc_Price4", "Inv_Loc_Price5"]:
        v[k] = prijs
    return v


N = [
    NieuwItem(kopie_retail("203025", Inv_Sku=None, Inv_Desc="Bulk 1024000, Prosciutto Crudo Mattonella",
                           Inv_VendorID="ONE TIME", Inv_DepartID="03. Vleeswaren",
                           Inv_ClassID="0301: Vleeswaren vers gesneden", Inv_Part_Vendor="1024000"),
              "Bulk voor PLU 3025 Prosciutto (Sjors). Prijzen en kostprijs van retail 203025.",
              ["Inv_Sku: bulk-SKU zelf aanmaken (2024700...)"]),
    NieuwItem(nieuw_retail(3120, "Lamsbout zonder been diepvries, p/kg", 20.20, 30.30, "VAN KOOTEN",
                           "02. Slagerij vers", "0202: Rund"),
              "Weegschaal-PLU 3120 staat niet in RE. Kostprijs = weegschaalcode/1000, prijs van de weegschaal. "
              "Klasse 0202 zoals Lamrack (203110).",
              ["Part nr Van Kooten onbekend", "Bulk-item nog aan te maken"]),
    NieuwItem(nieuw_retail(3217, "Kalfs hart zwezerik, p/kg", None, 83.36, None, "02. Slagerij vers", "0202: Rund"),
              "Weegschaal-PLU 3217 staat niet in RE. Prijs van de weegschaal.",
              ["Kostprijs onbekend", "Leverancier onbekend (weegschaal leeg)", "Bulk-item nog aan te maken"]),
    NieuwItem(nieuw_retail(3090, "Ham di Pasku bone in, p/kg", 7.35, 8.75, "HHB", "03. Vleeswaren",
                           "0301: Vleeswaren vers gesneden", "H6159-0001, Ham di Pasku bone in"),
              "Weegschaal-PLU 3090. Kostprijs/prijs/HHB-code van het oude item 2024700084939.",
              ["Oud item 2024700084939 (voorraad -2.485 kg) daarna omzetten naar bulk of opheffen"]),
    NieuwItem(nieuw_retail(3091, "Ham di Pasku boneless, p/kg", 9.68, 13.80, "HHB", "03. Vleeswaren",
                           "0301: Vleeswaren vers gesneden", "H6159-0005, Ham di Pasku boneless"),
              "Weegschaal-PLU 3091. Kostprijs/prijs/HHB-code van het oude item 2024700084946.",
              ["Oud item 2024700084946 (voorraad -538 kg) daarna omzetten naar bulk of opheffen"]),
]

T = [
    "RetailEdge-import 6-11-2026 (Kaas & Vlees administratie)",
    f"Bron: {re_pad.name} (locatie Main). Template: {template.name}.",
    "",
    "Tabblad 'Import bijwerken': bestaande items. Alle huidige RE-waarden zijn overgenomen; alleen de gele cellen veranderen.",
    "  Klaar om te importeren: het CSV-bestand '..._bijwerken.csv' naast dit bestand.",
    "Tabblad 'Import nieuw': nieuwe items. Rode cellen eerst invullen, dan het tabblad opslaan als CSV en importeren.",
    "  De bulk-SKU voor Prosciutto maak je zelf aan; ik verzin geen SKU's.",
    "Tabblad 'Overzicht': per regel wat er verandert en waarom.",
    "",
    "Niet opgenomen (bewust):",
    "  2135-2138 Droge worst: bestaan al als scan-artikel (2024700003534-565, part nr 1002135-1002138). Nieuwe 20213x-items zouden dubbel zijn.",
    "  3026 Iberico diepvries: dubbel met 3063 Iberico diepvries (staat al in RE als 203063). Van de weegschaal halen.",
    "  3043 Sausage links: leverancier 'MIS product cross dock' bestaat niet in RE en het nummer (14?) is niet zeker.",
    "  Kaas: part nrs van 1012, 1018, 1023, 1508, 1510, 1704 wachten op keuze retail- of bulknummer.",
    "  3039 Varkensrollade en 3562-3564 Kippendij: al door Sjors aangepast in RE.",
    "  3716 Gehakt Cordon Bleu: bulk 5180 Cordon bleu is 0201 Kip en draagt ook 3062 Kip Cordon Bleu Vries. Eerst bevestigen dat 3716 bij 5180 hoort.",
]

uit = uitvoermap(inst) / f"RetailEdge_Import_{datetime.now():%Y_%m_%d}.xlsx"
xlsx, csv_pad = schrijf(uit, koppen, re_df, W, N, T)
print(f"Bijwerken: {len(W)} regels | Nieuw: {len(N)} regels")
print(f"-> {xlsx}")
print(f"-> {csv_pad}")
