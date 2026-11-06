"""Bronbestanden inlezen, met duidelijke foutmeldingen als het formaat niet klopt.

Alles wordt eerst als tekst gelezen; getallen worden daarna pas omgezet.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from .instellingen import BronFout, Regels

RE_VERPLICHT = [
    "Inv_Sku", "Inv_Desc", "Inv_VendorID", "Inv_Part_Vendor", "Inv_DepartID",
    "Inv_ClassID", "Loc_Settings_LocID",
]
Z_VERPLICHT = ["Winkel", "Artikel", "Aantallen", "Gewicht"]
WEEGSCHAAL_KOLOMMEN = ["PLU", "Artikel", "Leverancier", "Bestelnummer", "_leeg1", "_leeg2", "Weegschaalcode", "Prijs"]
# indeling sinds 6-11-2026: kolom C is een groepnummer, daarna leverancier, bestelnummer, code, prijs
WEEGSCHAAL_KOLOMMEN_MET_GROEP = ["PLU", "Artikel", "Groep", "Leverancier", "Bestelnummer", "Weegschaalcode", "Prijs"]
MAPPING_KOPPEN = {"plu": "Portie PLU", "artnr": "Portie ART NR", "bulk": "Bulk SKU (RetailEdge)"}
NVT_BULK = "n.v.t. (zelfde artikel)"


# ---------------------------------------------------------------- hulpfuncties

def leeg(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return str(v).strip() == "" or str(v).strip().lower() == "nan"


def tekst(v) -> str:
    return "" if leeg(v) else str(v).strip()


def getal(v) -> Decimal | None:
    """Zet een celwaarde om naar een Decimal. Geeft None bij leeg of geen getal."""
    if leeg(v):
        return None
    if isinstance(v, (int, Decimal)):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    s = str(v).strip().replace(" ", "")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def geheel_getal(v) -> int | None:
    d = getal(v)
    if d is None or d != d.to_integral_value():
        return None
    return int(d)


def sku_tekst(v) -> str:
    """SKU als tekst zonder '.0' of wetenschappelijke notatie (13 cijfers passen niet in Excel-integers)."""
    if leeg(v):
        return ""
    d = getal(v)
    if d is not None and d == d.to_integral_value():
        return str(int(d))
    return str(v).strip()


# ---------------------------------------------------------------- RetailEdge

def lees_re_export(pad: Path, regels: Regels) -> pd.DataFrame:
    """RE inventory-export (cp1252). Geeft alleen de hoofdlocatie, index = Inv_Sku."""
    try:
        df = pd.read_csv(pad, dtype=str, encoding=regels.re_encoding, low_memory=False, keep_default_na=False)
    except UnicodeDecodeError as e:
        raise BronFout(f"RE-export is niet in {regels.re_encoding} opgeslagen: {pad.name} ({e})") from e
    ontbreekt = [k for k in RE_VERPLICHT if k not in df.columns]
    if ontbreekt:
        raise BronFout(f"RE-export {pad.name} mist kolommen: {', '.join(ontbreekt)}. Is dit wel een inventory-export?")
    df = df.apply(lambda s: s.str.strip())
    df = df[df.Loc_Settings_LocID == regels.hoofdlocatie]
    if df.empty:
        raise BronFout(f"RE-export {pad.name} bevat geen regels voor locatie '{regels.hoofdlocatie}'.")
    dubbel = df.Inv_Sku[df.Inv_Sku.duplicated()].unique()
    if len(dubbel):
        raise BronFout(f"RE-export {pad.name} bevat dubbele SKU's: {', '.join(dubbel[:10])}")
    return df.set_index("Inv_Sku", drop=False)


# ---------------------------------------------------------------- weegschaal

def lees_weegschaal(pad: Path) -> pd.DataFrame:
    """Weegschaal item-overzicht (xlsx zonder kopregel). Kolom PLU wordt int."""
    df = pd.read_excel(pad, header=None, dtype=str)
    if df.shape[1] < 4:
        raise BronFout(f"Weegschaal-lijst {pad.name} heeft {df.shape[1]} kolommen, verwacht minstens 4 (PLU, Artikel, Leverancier, Bestelnummer).")
    # Indeling herkennen: staat in kolom C een groepnummer (cijfers) of een leveranciersnaam?
    kol_c = df.iloc[:, 2].dropna().astype(str).str.strip()
    met_groep = len(kol_c) > 0 and kol_c.str.fullmatch(r"\d+").mean() > 0.9
    kolommen = WEEGSCHAAL_KOLOMMEN_MET_GROEP if met_groep else WEEGSCHAAL_KOLOMMEN
    df = df.iloc[:, : len(kolommen)]
    df.columns = kolommen[: df.shape[1]]
    df["PLU"] = df.PLU.map(geheel_getal)
    df = df[df.PLU.notna()].copy()
    if df.empty:
        raise BronFout(f"Weegschaal-lijst {pad.name} bevat geen PLU-nummers in kolom A.")
    df["PLU"] = df.PLU.astype(int)
    for k in ("Artikel", "Leverancier", "Bestelnummer"):
        df[k] = df[k].map(tekst)
    dubbel = df.PLU[df.PLU.duplicated()].unique()
    if len(dubbel):
        raise BronFout(f"Weegschaal-lijst {pad.name} bevat dubbele PLU's: {', '.join(map(str, dubbel))}")
    return df.drop(columns=[c for c in df.columns if c.startswith("_")]).reset_index(drop=True)


# ---------------------------------------------------------------- Z-afslag

def lees_z_afslag(pad: Path) -> pd.DataFrame:
    """Z-afslag van de weegschaal (.xls, .xlsx of .csv), eerste tabblad, kopregel op rij 1."""
    ext = pad.suffix.lower()
    if ext in (".xls", ".xlsx", ".xlsm"):
        df = pd.read_excel(pad, sheet_name=0, dtype=str)
    elif ext == ".csv":
        with open(pad, encoding="utf-8-sig", errors="replace") as f:
            voorbeeld = f.read(4096)
        try:
            sep = csv.Sniffer().sniff(voorbeeld, delimiters=",;\t").delimiter
        except csv.Error:
            sep = ","
        df = pd.read_csv(pad, sep=sep, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    else:
        raise BronFout(f"Onbekend bestandstype voor Z-afslag: {pad.name} (verwacht .xls, .xlsx of .csv)")
    df.columns = [str(c).strip() for c in df.columns]
    ontbreekt = [k for k in Z_VERPLICHT if k not in df.columns]
    if ontbreekt:
        raise BronFout(f"Z-afslag {pad.name}: verwachte kolommen niet gevonden: {', '.join(ontbreekt)}.")
    return df


# ---------------------------------------------------------------- mappingtabel

@dataclass
class MappingRegel:
    plu: int
    artnr: str
    bulk_sku: str  # "" = geen bulk (1-op-1 of nog open)
    tabblad: str
    rij: int


@dataclass
class Mapping:
    regels: dict[int, MappingRegel] = field(default_factory=dict)
    meldingen: list[str] = field(default_factory=list)
    tabbladen: list[str] = field(default_factory=list)


def _kop(v) -> str:
    s = tekst(v)
    while s.endswith("*"):
        s = s[:-1].strip()
    return s


def lees_mappingtabel(pad: Path, menu_tabblad: str = "PICS import") -> Mapping:
    """Mappingtabel(len) lezen zoals de PICS-macro dat doet: elk tabblad met de juiste kolomkoppen.

    Verschillen met de macro: tabbladen zonder de koppen (bijv. 'Uitleg') worden overgeslagen
    in plaats van een fout te geven, en een dubbele PLU geeft een melding (de macro neemt
    stilzwijgend de laatste).
    """
    from openpyxl import load_workbook

    try:
        wb = load_workbook(pad, read_only=True, data_only=True, keep_vba=False)
    except Exception as e:  # noqa: BLE001 - openpyxl geeft diverse fouttypen
        raise BronFout(f"Mappingtabel {pad.name} kan niet geopend worden: {e}") from e
    m = Mapping()
    try:
        for ws in wb.worksheets:
            if ws.title == menu_tabblad:
                continue
            rijen = ws.iter_rows(values_only=True)
            koppen = [_kop(v) for v in next(rijen, ())]
            try:
                kol = {k: koppen.index(naam) for k, naam in MAPPING_KOPPEN.items()}
            except ValueError:
                continue
            m.tabbladen.append(ws.title)
            for nr, rij in enumerate(rijen, start=2):
                def cel(k):
                    i = kol[k]
                    return rij[i] if i < len(rij) else None
                plu = geheel_getal(cel("plu"))
                if plu is None:
                    if not leeg(cel("plu")):
                        m.meldingen.append(f"{ws.title} rij {nr}: PLU '{cel('plu')}' is geen getal, overgeslagen.")
                    continue
                artnr = geheel_getal(cel("artnr"))
                if artnr is None:
                    m.meldingen.append(f"{ws.title} rij {nr}: PLU {plu} heeft geen geldig Portie ART NR, overgeslagen.")
                    continue
                bulk_ruw = tekst(cel("bulk"))
                bulk = "" if bulk_ruw in ("", NVT_BULK) else sku_tekst(bulk_ruw)
                if bulk and not bulk.isdigit():
                    m.meldingen.append(f"{ws.title} rij {nr}: PLU {plu} heeft bulk SKU '{bulk_ruw}' (geen nummer); behandeld als zonder bulk.")
                    bulk = ""
                if plu in m.regels:
                    oud = m.regels[plu]
                    m.meldingen.append(
                        f"PLU {plu} staat dubbel: {oud.tabblad} rij {oud.rij} en {ws.title} rij {nr}. De laatste wordt gebruikt (zoals de macro).")
                m.regels[plu] = MappingRegel(plu, str(artnr), bulk, ws.title, nr)
    finally:
        wb.close()
    if not m.tabbladen:
        raise BronFout(
            f"Mappingtabel {pad.name}: geen tabblad met de kolommen {', '.join(MAPPING_KOPPEN.values())} gevonden.")
    return m
