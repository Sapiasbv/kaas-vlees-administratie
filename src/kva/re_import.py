"""RetailEdge-importbestand maken volgens het 'RetailEdge CSV Inventory Import Template'.

Bijwerken van bestaande items: alle huidige kolomwaarden uit de RE-export worden overgenomen,
alleen de opgegeven velden veranderen (anders overschrijft RE ze met leeg).
Nieuwe items: alleen wat bekend is; Inv_Sku van een nieuw bulk-item blijft leeg (maakt de gebruiker aan).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .bronnen import leeg

# kolommen die in de import anders heten dan in de export
IMPORT_NAAR_EXPORT = {"User Field 4": "Text on Price Tag", "CustomSubTotal1": "EBT", "CustomSubTotal2": "DUFB"}
BOOLEANS = {"Inv_Loc_Taxable", "Inv_Loc_DenySales", "Inv_Cost_Dynamic", "CustomSubTotal1", "CustomSubTotal2", "CustomSubTotal3"}
TEKST = {"Inv_Sku", "Inv_ItemID", "Inv_Part_Vendor", "Inv_Part_Mfr", "Inv_UPC1", "Inv_UPC2", "Inv_Desc",
         "Inv_VendorID", "Inv_DepartID", "Inv_ClassID", "Inv_Weight_Unit", "Inv_ExpCode", "Inv_Loc_BinShelf",
         "Inv_QuanPriceOptions", "User Field 1", "User Field 2", "User Field 3", "User Field 4", "User Field 5"}
VERPLICHT_NIEUW = ["Inv_Sku", "Inv_Desc", "Inv_Cost_Last", "Inv_Loc_Price1", "Inv_VendorID", "Inv_DepartID", "Inv_ClassID"]
ROOD = PatternFill("solid", fgColor="F8CBAD")
GEEL = PatternFill("solid", fgColor="FFF2CC")
KOP = PatternFill("solid", fgColor="1F3864")


def _getal_tekst(v: float) -> str:
    return ("%.6f" % v).rstrip("0").rstrip(".")


def template_koppen(template: Path) -> list[str]:
    ws = load_workbook(template, read_only=True).worksheets[0]
    return [str(c).strip() for c in next(ws.iter_rows(max_row=1, values_only=True)) if c is not None]


def _waarde(kop: str, v):
    if leeg(v):
        return None
    if kop in BOOLEANS:
        return str(v).strip().lower() == "true" if not isinstance(v, bool) else v
    if kop in TEKST:
        return str(v).strip()
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v).strip()


@dataclass
class Wijziging:
    sku: str
    velden: dict[str, object]
    reden: str


@dataclass
class NieuwItem:
    velden: dict[str, object]
    reden: str
    open_punten: list[str] = field(default_factory=list)


def bijwerk_rij(koppen: list[str], item: pd.Series, w: Wijziging) -> list:
    rij = []
    for kop in koppen:
        bron = IMPORT_NAAR_EXPORT.get(kop, kop)
        v = item[bron] if bron in item.index else None
        if kop in w.velden:
            v = w.velden[kop]
        rij.append(_waarde(kop, v))
    return rij


def nieuw_rij(koppen: list[str], n: NieuwItem) -> list:
    return [_waarde(k, n.velden.get(k)) for k in koppen]


def controleer(re_df: pd.DataFrame, wijzigingen: list[Wijziging], nieuw: list[NieuwItem]) -> list[str]:
    fouten = []
    gezien = set()
    for w in wijzigingen:
        if w.sku not in re_df.index:
            fouten.append(f"Bijwerken: SKU {w.sku} staat niet in de RE-export.")
        if w.sku in gezien:
            fouten.append(f"Bijwerken: SKU {w.sku} staat dubbel.")
        gezien.add(w.sku)
    for n in nieuw:
        sku = n.velden.get("Inv_Sku")
        if sku and str(sku) in re_df.index:
            fouten.append(f"Nieuw: SKU {sku} bestaat al in RE.")
    return fouten


def schrijf(pad: Path, koppen: list[str], re_df: pd.DataFrame, wijzigingen: list[Wijziging],
            nieuw: list[NieuwItem], toelichting: list[str]) -> tuple[Path, Path | None]:
    if pad.exists():
        raise FileExistsError(f"Bestaat al, niet overschreven: {pad}")
    fouten = controleer(re_df, wijzigingen, nieuw)
    if fouten:
        raise ValueError("\n".join(fouten))
    wb = Workbook()
    uitleg = wb.active
    uitleg.title = "Toelichting"
    for i, t in enumerate(toelichting, 1):
        uitleg.cell(i, 1, t).font = Font(bold=(i == 1), size=13 if i == 1 else 11)
    uitleg.column_dimensions["A"].width = 150

    def blad(titel, rijen, markeer):
        ws = wb.create_sheet(titel)
        ws.append(koppen)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = KOP
        for r in rijen:
            ws.append(r)
        for j in range(1, len(koppen) + 1):
            ws.column_dimensions[get_column_letter(j)].width = 16
        ws.column_dimensions["B"].width = 42
        ws.freeze_panes = "C2"
        markeer(ws)
        return ws

    kol = {k: i for i, k in enumerate(koppen)}

    def markeer_bij(ws):
        for r, w in enumerate(wijzigingen, start=2):
            for veld in w.velden:
                ws.cell(r, kol[veld] + 1).fill = GEEL

    def markeer_nieuw(ws):
        for r, n in enumerate(nieuw, start=2):
            for veld in VERPLICHT_NIEUW:
                if leeg(n.velden.get(veld)):
                    ws.cell(r, kol[veld] + 1).fill = ROOD

    bij_rijen = [bijwerk_rij(koppen, re_df.loc[w.sku], w) for w in wijzigingen]
    blad("Import bijwerken", bij_rijen, markeer_bij)
    blad("Import nieuw", [nieuw_rij(koppen, n) for n in nieuw], markeer_nieuw)

    ov = wb.create_sheet("Overzicht")
    ov.append(["Soort", "SKU", "Omschrijving", "Wat verandert", "Reden", "Nog in te vullen"])
    for c in ov[1]:
        c.font = Font(bold=True)
    for w in wijzigingen:
        oud = re_df.loc[w.sku]
        wat = "; ".join(f"{k}: {oud.get(IMPORT_NAAR_EXPORT.get(k, k), '') or '(leeg)'} -> {v}" for k, v in w.velden.items())
        ov.append(["Bijwerken", w.sku, oud.Inv_Desc, wat, w.reden, None])
    for n in nieuw:
        ov.append(["Nieuw", n.velden.get("Inv_Sku") or "(SKU zelf aanmaken)", n.velden.get("Inv_Desc"), "Nieuw item",
                   n.reden, "; ".join(n.open_punten) or None])
    for j, b in enumerate([10, 16, 40, 90, 70, 50], 1):
        ov.column_dimensions[get_column_letter(j)].width = b
    pad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pad)

    # CSV voor het bijwerken (direct te importeren); nieuw pas na invullen van de rode cellen
    csv_pad = None
    if bij_rijen:
        csv_pad = pad.with_name(pad.stem + "_bijwerken.csv")
        if csv_pad.exists():
            raise FileExistsError(f"Bestaat al, niet overschreven: {csv_pad}")
        with open(csv_pad, "w", encoding="cp1252", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(koppen)
            for r in bij_rijen:
                wr.writerow(["TRUE" if v is True else "FALSE" if v is False else ("" if v is None else
                             (_getal_tekst(v) if isinstance(v, float) else v)) for v in r])
    return pad, csv_pad
