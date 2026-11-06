"""Voorraadlijst (bulk en stuks) uit de RE-export, tellijsten in een vast Excel-formaat, en telverschillen.

Tellijst-formaat (versie 1), zodat een ingevulde lijst weer ingelezen kan worden:
- tabblad 'Info'    : kenmerk KVA-tellijst, versie, gemaakt op, RE-export.
- tabblad 'Tellijst bulk' en/of 'Tellijst stuks': kopregel met o.a. SKU, Omschrijving, Eenheid, Geteld, Opmerking.
- tabblad 'Systeem' (verborgen): RE-voorraad en kostprijs op het moment van uitdraaien.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .bronnen import getal, tekst
from .instellingen import BronFout, Regels
from .koppeling import Koppelresultaat

KENMERK = "KVA-tellijst"
VERSIE = "1"
BULK, STUK = "Bulk", "Stuk"
TABBLAD = {BULK: "Tellijst bulk", STUK: "Tellijst stuks"}
LIJST_KOLOMMEN = ["Soort", "Type", "Afdeling", "SKU", "PLU", "Omschrijving", "Leverancier", "Eenheid",
                  "Voorraad", "Kostprijs", "Waarde", "Gekoppeld"]
TEL_KOLOMMEN = ["Nr", "Afdeling", "SKU", "PLU", "Omschrijving", "Eenheid", "Geteld", "Opmerking"]
PER_STUK = re.compile(r"(?i)(p/st|per stuk)\b")

KOP = PatternFill("solid", fgColor="1F3864")
INVUL = PatternFill("solid", fgColor="FFF9DB")
DUN = Side(style="thin", color="B4C6E7")
RAND = Border(left=DUN, right=DUN, top=DUN, bottom=DUN)


def _f(v) -> float:
    g = getal(v)
    return float(g) if g is not None else 0.0


# ---------------------------------------------------------------- voorraadlijst

def voorraad_lijst(re_df: pd.DataFrame, koppelingen: list[Koppelresultaat], regels: Regels) -> pd.DataFrame:
    """Alle bulk- en stuksartikelen (vlees en kaas) met de voorraad volgens de RE-export."""
    per_stuk = regels.afslag_indeling.get("per_stuk", {})
    rijen = []
    for k in koppelingen:
        soort = k.soort.capitalize()
        plus = k.plus if not k.plus.empty else pd.DataFrame(columns=["PLU", "artnr", "bulk_sku"])
        per_bulk = plus[plus.bulk_sku.ne("")].groupby("bulk_sku").PLU.apply(lambda s: sorted(int(x) for x in s))
        for sku in k.bulks.Inv_Sku:
            item = re_df.loc[sku]
            gekoppeld = per_bulk.get(sku, [])
            eenheid = "st" if any(per_stuk.get(str(p)) == "stuk" for p in gekoppeld) else "kg"
            rijen.append(_rij(soort, BULK, item, None, eenheid, ", ".join(map(str, gekoppeld))))
        for r in plus.itertuples(index=False):
            item = re_df.loc[r.artnr]
            eenheid = "st" if PER_STUK.search(tekst(item.Inv_Desc)) else "kg"
            rijen.append(_rij(soort, STUK, item, int(r.PLU), eenheid, r.bulk_sku))
    df = pd.DataFrame(rijen, columns=LIJST_KOLOMMEN)
    return df.sort_values(["Type", "Soort", "Afdeling", "Omschrijving"], key=lambda s: s.str.lower()).reset_index(drop=True)


def _rij(soort, type_, item, plu, eenheid, gekoppeld) -> dict:
    q, kost = _f(item.Inv_Quan), _f(item.Inv_Cost_Last)
    return {"Soort": soort, "Type": type_, "Afdeling": tekst(item.Inv_DepartID), "SKU": tekst(item.Inv_Sku),
            "PLU": plu, "Omschrijving": re.sub(r"\s+", " ", tekst(item.Inv_Desc)),
            "Leverancier": tekst(item.Inv_VendorID), "Eenheid": eenheid, "Voorraad": round(q, 3),
            "Kostprijs": round(kost, 2), "Waarde": round(q * kost, 2), "Gekoppeld": gekoppeld}


# ---------------------------------------------------------------- tellijst maken

def maak_tellijst(lijst: pd.DataFrame, pad: Path, bron: str, toon_voorraad: bool = False) -> Path:
    """Excel met een tabblad per type (bulk/stuks), klaar om te printen en in te vullen."""
    if pad.exists():
        raise FileExistsError(f"Bestaat al: {pad}")
    wb = Workbook()
    info = wb.active
    info.title = "Info"
    nu = datetime.now()
    for r in [("Kenmerk", KENMERK), ("Versie", VERSIE), ("Gemaakt op", nu.strftime("%Y-%m-%d %H:%M")),
              ("RE-export", bron), ("Artikelen", len(lijst)),
              ("Uitleg", "Vul per artikel de kolom 'Geteld' in (kg of stuks, zie kolom Eenheid). "
                         "Niet gevonden = 0 invullen. Leeg laten = niet geteld. Lever het bestand daarna weer aan.")]:
        info.append(r)
    info.column_dimensions["A"].width = 14
    info.column_dimensions["B"].width = 110

    kolommen = TEL_KOLOMMEN[:6] + (["Systeem"] if toon_voorraad else []) + TEL_KOLOMMEN[6:]
    for type_ in (BULK, STUK):
        deel = lijst[lijst.Type == type_]
        if deel.empty:
            continue
        ws = wb.create_sheet(TABBLAD[type_])
        ws.append([f"{TABBLAD[type_]} kaas & vlees — uitgedraaid {nu:%d-%m-%Y %H:%M}"])
        ws["A1"].font = Font(bold=True, size=14)
        ws.append(["Datum telling: ____________    Geteld door: ________________________    "
                   "Vul Geteld in; niet gevonden = 0"])
        ws.append([])
        ws.append(kolommen)
        for c in ws[4]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = KOP
            c.alignment = Alignment(vertical="center")
        for nr, r in enumerate(deel.itertuples(index=False), start=1):
            rij = [nr, r.Afdeling, r.SKU, r.PLU if pd.notna(r.PLU) else None, r.Omschrijving, r.Eenheid]
            if toon_voorraad:
                rij.append(r.Voorraad)
            ws.append(rij + [None, None])
            for c in ws[ws.max_row]:
                c.border = RAND
            ws.cell(ws.max_row, kolommen.index("Geteld") + 1).fill = INVUL
            ws.cell(ws.max_row, kolommen.index("SKU") + 1).number_format = "@"
        breedte = {"Nr": 5, "Afdeling": 18, "SKU": 16, "PLU": 7, "Omschrijving": 46, "Eenheid": 8,
                   "Systeem": 10, "Geteld": 12, "Opmerking": 28}
        for j, k in enumerate(kolommen, start=1):
            ws.column_dimensions[get_column_letter(j)].width = breedte[k]
        ws.freeze_panes = "A5"
        ws.print_title_rows = "4:4"
        ws.page_setup.orientation = "portrait"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.gridLines = True
        ws.oddFooter.center.text = "Pagina &P van &N"

    sys_ = wb.create_sheet("Systeem")
    sys_.append(["SKU", "Type", "Soort", "Omschrijving", "Eenheid", "Voorraad", "Kostprijs"])
    for r in lijst.itertuples(index=False):
        sys_.append([r.SKU, r.Type, r.Soort, r.Omschrijving, r.Eenheid, r.Voorraad, r.Kostprijs])
    sys_.sheet_state = "hidden"
    wb.active = 1 if len(wb.sheetnames) > 2 else 0
    pad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pad)
    return pad


# ---------------------------------------------------------------- tellijst inlezen

@dataclass
class Telling:
    info: dict[str, str]
    geteld: pd.DataFrame        # SKU, Type, Geteld, Opmerking (alleen ingevulde regels)
    niet_geteld: int
    systeem: pd.DataFrame       # snapshot uit het verborgen tabblad


def lees_tellijst(pad) -> Telling:
    wb = load_workbook(pad, data_only=True)
    if "Info" not in wb.sheetnames:
        raise BronFout("Dit is geen tellijst uit deze app (tabblad 'Info' ontbreekt).")
    info = {tekst(a): tekst(b) for a, b, *_ in wb["Info"].iter_rows(values_only=True) if a}
    if info.get("Kenmerk") != KENMERK:
        raise BronFout("Dit is geen tellijst uit deze app (kenmerk ontbreekt).")
    rijen, niet = [], 0
    for type_, naam in TABBLAD.items():
        if naam not in wb.sheetnames:
            continue
        ws = wb[naam]
        kop_rij, kol = None, {}
        for i, rij in enumerate(ws.iter_rows(values_only=True), start=1):
            if kop_rij is None:
                if rij and "SKU" in rij and "Geteld" in rij:
                    kop_rij, kol = i, {tekst(k): j for j, k in enumerate(rij) if k}
                continue
            sku = tekst(rij[kol["SKU"]]).removesuffix(".0")
            if not sku:
                continue
            ruw = rij[kol["Geteld"]]
            if ruw is None or tekst(ruw) == "":
                niet += 1
                continue
            g = getal(ruw)
            if g is None:
                raise BronFout(f"{naam}: SKU {sku} heeft geen geldig getal bij Geteld ('{ruw}').")
            rijen.append({"SKU": sku, "Type": type_, "Geteld": float(g),
                          "Opmerking": tekst(rij[kol["Opmerking"]]) if "Opmerking" in kol else ""})
        if kop_rij is None:
            raise BronFout(f"{naam}: kopregel met SKU en Geteld niet gevonden.")
    systeem = pd.DataFrame(columns=["SKU", "Type", "Soort", "Omschrijving", "Eenheid", "Voorraad", "Kostprijs"])
    if "Systeem" in wb.sheetnames:
        s = list(wb["Systeem"].iter_rows(values_only=True))
        systeem = pd.DataFrame(s[1:], columns=s[0])
        systeem["SKU"] = systeem.SKU.map(lambda v: tekst(v).removesuffix(".0"))
    return Telling(info, pd.DataFrame(rijen, columns=["SKU", "Type", "Geteld", "Opmerking"]), niet, systeem)


def telverschillen(t: Telling, re_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Geteld tegen de RE-voorraad bij het uitdraaien (en, als gegeven, tegen de huidige RE-export)."""
    sys_ = t.systeem.set_index("SKU")
    uit = []
    for r in t.geteld.itertuples(index=False):
        s = sys_.loc[r.SKU] if r.SKU in sys_.index else None
        voorraad = float(s.Voorraad) if s is not None and pd.notna(s.Voorraad) else None
        kost = float(s.Kostprijs) if s is not None and pd.notna(s.Kostprijs) else None
        rij = {"Type": r.Type, "Soort": s.Soort if s is not None else "", "SKU": r.SKU,
               "Omschrijving": s.Omschrijving if s is not None else "", "Eenheid": s.Eenheid if s is not None else "",
               "Systeem bij uitdraai": voorraad, "Geteld": r.Geteld,
               "Verschil": round(r.Geteld - voorraad, 3) if voorraad is not None else None,
               "Kostprijs": kost, "Opmerking": r.Opmerking}
        rij["Waarde verschil"] = round(rij["Verschil"] * kost, 2) if rij["Verschil"] is not None and kost else None
        if re_df is not None:
            rij["RE nu"] = round(_f(re_df.at[r.SKU, "Inv_Quan"]), 3) if r.SKU in re_df.index else None
        uit.append(rij)
    df = pd.DataFrame(uit)
    if df.empty:
        return df
    return df.sort_values("Waarde verschil", key=lambda s: s.abs().fillna(0), ascending=False).reset_index(drop=True)
