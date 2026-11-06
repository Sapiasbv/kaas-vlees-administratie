"""Maandcontrole: productie van de weegschaal (Z-afslagen) tegen de verkoop in RetailEdge.

RE-rapport: Reports > 'Sales by Items - Grouped by Location', presets 'Summary Report' en 'Department only',
opslaan als 'Excel File - Data (*.xls)'. Geen kopregel; kolommen:
A SKU, B item (eenheid @ prijs, eventueel '(MAN WT)', omschrijving), C aantal/kg, D kostprijs totaal,
E verkoop totaal, F marge $, G korting %, H marge %, I aandeel van de omzet.
Lange omschrijvingen lopen door op de volgende rij (kolom A leeg); die worden aan de regel erboven geplakt.
De eenheid 'lb' in kolom B is alleen een label: de hoeveelheid is in kg (prijs per eenheid = kg-prijs).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .bronnen import getal, tekst
from .instellingen import BronFout, Regels
from .koppeling import Koppelresultaat, plu_naar_artnr
from .verwerking import KAAS, KAAS_GEEN_BULK, VLEES, VLEES_GEEN_BULK, deel_in, mapping_uit_koppeling

VERKOOP_KOLOMMEN = ["SKU", "Item", "Aantal", "Kost", "Omzet", "Marge", "Korting", "Marge %", "Aandeel"]
ITEM = re.compile(r"^\s*(?P<eenheid>kg|lb|ea|st)?\s*@\s*\$?(?P<prijs>[\d.,]+)\s*/\s*\w+\s*(?P<man>\(MAN WT\))?\s*(?P<naam>.*)$", re.I)
PERIODE = re.compile(r"van_(\d{8})_tm_(\d{8})")


def _bedrag(v) -> float:
    s = tekst(v).replace("$", "").replace(",", "").replace("%", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    g = getal(s.strip("()"))
    return float(-g if neg else g) if g is not None else 0.0


def lees_re_verkoop(pad) -> pd.DataFrame:
    """RE 'Sales by Items' (.xls) -> een rij per SKU met aantal, kost, omzet en of er met de hand is gewogen."""
    try:
        ruw = pd.read_excel(pad, header=None, dtype=str)
    except Exception as e:  # noqa: BLE001
        raise BronFout(f"Verkoopexport kan niet gelezen worden: {e}") from None
    if ruw.shape[1] < 5:
        raise BronFout(f"Verkoopexport heeft {ruw.shape[1]} kolommen, verwacht 9 (SKU, item, aantal, kost, omzet, ...).")
    ruw = ruw.iloc[:, :9]
    ruw.columns = VERKOOP_KOLOMMEN[: ruw.shape[1]]
    rijen: list[dict] = []
    for r in ruw.to_dict("records"):
        sku = tekst(r["SKU"]).removesuffix(".0")
        if not sku:
            if rijen and tekst(r["Item"]):
                rijen[-1]["Item"] += " " + tekst(r["Item"])  # doorlopende omschrijving
            continue
        if not sku.isdigit():
            continue  # kop- of totaalregel
        rijen.append(dict(r, SKU=sku, Item=tekst(r["Item"])))
    if not rijen:
        raise BronFout("Geen artikelregels gevonden in de verkoopexport (kolom A moet SKU's bevatten).")
    uit = []
    for r in rijen:
        m = ITEM.match(r["Item"])
        uit.append({
            "SKU": r["SKU"],
            "Omschrijving RE": (m["naam"] if m else r["Item"]).strip(),
            "Prijs RE": float(getal(m["prijs"].replace(",", ""))) if m else None,
            "Handmatig gewogen": bool(m and m["man"]),
            "Verkocht": _bedrag(r["Aantal"]),
            "Kost": _bedrag(r["Kost"]),
            "Omzet": _bedrag(r["Omzet"]),
        })
    df = pd.DataFrame(uit)
    # meerdere regels per SKU (andere prijs of handmatig) optellen
    return (df.groupby("SKU", as_index=False)
              .agg({"Omschrijving RE": "first", "Prijs RE": "last", "Handmatig gewogen": "any",
                    "Verkocht": "sum", "Kost": "sum", "Omzet": "sum"}))


def periode_uit_naam(naam: str) -> tuple[date, date] | None:
    m = PERIODE.search(naam)
    if not m:
        return None
    try:
        return tuple(date(int(x[:4]), int(x[4:6]), int(x[6:])) for x in m.groups())  # type: ignore[return-value]
    except ValueError:
        return None


def controleer_dekking(perioden: list[tuple[date, date]], van: date, tm: date) -> list[str]:
    """Dekken de Z-afslagen precies de periode van de RE-export, zonder gaten of overlap?"""
    if not perioden:
        return ["Periode van de Z-afslag(en) niet te herkennen uit de bestandsnaam."]
    m = []
    p = sorted(perioden)
    if p[0][0] != van or p[-1][1] != tm:
        m.append(f"Z-afslagen lopen van {p[0][0]:%d-%m-%Y} t/m {p[-1][1]:%d-%m-%Y}, "
                 f"de RE-verkoop van {van:%d-%m-%Y} t/m {tm:%d-%m-%Y}. Vergelijk dezelfde periode.")
    for (a1, b1), (a2, b2) in zip(p, p[1:]):
        if (a2 - b1).days > 1:
            m.append(f"Gat tussen de Z-afslagen: {b1:%d-%m} en {a2:%d-%m}.")
        elif a2 <= b1:
            m.append(f"Z-afslagen overlappen: {a2:%d-%m} t/m {b1:%d-%m} telt dubbel.")
    return m


@dataclass
class Vergelijking:
    tabel: pd.DataFrame
    productie_kg: float
    verkocht_kg: float
    productie_st: float
    verkocht_st: float
    waarde_verschil: float


def vergelijk(z_afslagen: list[pd.DataFrame], verkoop: pd.DataFrame, koppelingen: list[Koppelresultaat],
              regels: Regels, re_df: pd.DataFrame | None = None, drempel_pct: float = 5.0,
              drempel_kg: float = 0.5) -> Vergelijking:
    """Per PLU: geproduceerd (Z-afslag) tegen verkocht (RE). Alleen vlees en kaas."""
    k_vlees = next(k for k in koppelingen if k.soort == "vlees")
    k_kaas = next((k for k in koppelingen if k.soort == "kaas"), None)
    m_vlees, m_kaas = mapping_uit_koppeling(k_vlees), mapping_uit_koppeling(k_kaas) if k_kaas else None
    soort_van = {int(p): k.soort.capitalize() for k in koppelingen if not k.plus.empty for p in k.plus.PLU}

    prod: dict[int, dict] = {}
    for z in z_afslagen:
        t = deel_in(z, m_vlees, m_kaas, regels, re_df).tabel
        t = t[t.Categorie.isin([VLEES, VLEES_GEEN_BULK, KAAS, KAAS_GEEN_BULK])]
        for r in t.itertuples(index=False):
            p = prod.setdefault(int(r.PLU), {"Omschrijving": r.Omschrijving, "kg": 0.0, "st": 0.0,
                                             "Soort": "Kaas" if r.Categorie.startswith("Kaas") else "Vlees"})
            p[r.Eenheid] += float(r.Hoeveelheid)

    v = verkoop.set_index("SKU")
    plus = set(prod) | set(soort_van)
    rijen = []
    for plu in sorted(plus):
        sku = plu_naar_artnr(plu)
        p = prod.get(plu)
        s = v.loc[sku] if sku in v.index else None
        if p is None and s is None:
            continue
        eenheid = "st" if p and p["st"] and not p["kg"] else "kg"
        if p is None and s is not None and re.search(r"(?i)p/st|per stuk", s["Omschrijving RE"]):
            eenheid = "st"
        gemaakt = (p[eenheid] if p else 0.0)
        verkocht = float(s.Verkocht) if s is not None else 0.0
        prijs = (float(s.Omzet) / verkocht) if s is not None and verkocht else (s["Prijs RE"] if s is not None else None)
        kost = (float(s.Kost) / verkocht) if s is not None and verkocht else None
        verschil = round(gemaakt - verkocht, 3)
        pct = round(100 * verschil / gemaakt, 1) if gemaakt else None
        if abs(verschil) <= max(drempel_kg if eenheid == "kg" else 0.5, abs(gemaakt) * drempel_pct / 100):
            status = "OK"
        elif verschil > 0:
            status = "Minder verkocht dan geproduceerd"
        else:
            status = "Meer verkocht dan geproduceerd"
        if p is None:
            status = "Verkocht, niet op de weegschaal"
        elif s is None:
            status = "Geproduceerd, niet verkocht in RE"
        rijen.append({
            "Status": status, "Soort": soort_van.get(plu) or (p["Soort"] if p else ""), "PLU": plu, "SKU": sku,
            "Omschrijving": p["Omschrijving"] if p else s["Omschrijving RE"], "Eenheid": eenheid,
            "Geproduceerd": round(gemaakt, 3), "Verkocht": round(verkocht, 3), "Verschil": verschil,
            "Verschil %": pct, "Verkoopprijs": round(prijs, 2) if prijs else None,
            "Waarde verschil (verkoop)": round(verschil * prijs, 2) if prijs else None,
            "Waarde verschil (kost)": round(verschil * kost, 2) if kost else None,
            "Handmatig gewogen": bool(s is not None and s["Handmatig gewogen"]),
        })
    df = pd.DataFrame(rijen)
    if not df.empty:
        df = df.sort_values("Waarde verschil (verkoop)", key=lambda x: -x.fillna(0).abs()).reset_index(drop=True)
    kg, st_ = df[df.Eenheid == "kg"] if not df.empty else df, df[df.Eenheid == "st"] if not df.empty else df
    return Vergelijking(df, float(kg.Geproduceerd.sum()) if len(kg) else 0.0, float(kg.Verkocht.sum()) if len(kg) else 0.0,
                        float(st_.Geproduceerd.sum()) if len(st_) else 0.0, float(st_.Verkocht.sum()) if len(st_) else 0.0,
                        float(df["Waarde verschil (verkoop)"].fillna(0).sum()) if len(df) else 0.0)


def archiveer(map_: Path, naam: str, data: bytes) -> Path:
    """Upload bewaren (zonder te overschrijven) zodat lees_z_afslag een pad heeft."""
    from .opslag import sha256, vrije_naam
    map_.mkdir(parents=True, exist_ok=True)
    pad = map_ / naam
    if pad.exists() and sha256(pad.read_bytes()) == sha256(data):
        return pad
    pad = vrije_naam(pad)
    pad.write_bytes(data)
    return pad


_ = Decimal  # (gebruikt via getal)
