"""Koppelcontrole: welke PLU (vlees of kaas) hoort bij welk bulk-item in RetailEdge.

Regels (zie config/mapping_rules.json):
1. part nr: het part nr van de retail-PLU is gelijk aan dat van de bulk, of begint met het
   bulknummer ('2145, Serranoham' -> '2145'), of de tekst achter de komma is gelijk.
2. naam (alleen waar 'naam_koppeling' aan staat, bijv. kaas): 'Stuk Maasdam, p/kg' hoort bij
   'Bulk Maasdam, p/kg'. Wijkt het part nr dan af, dan komt er een melding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .instellingen import Regels

BULK_NAAM = re.compile(r"(?i)^\s*bulk\b")
SOORTEN = ("vlees", "kaas")


def plu_naar_artnr(plu: int) -> str:
    return str(200000 + int(plu))


def _voor_komma(s: str) -> str:
    return s.split(",", 1)[0].strip().lower()


def _na_komma(s: str) -> str:
    return s.split(",", 1)[1].strip().lower() if "," in s else ""


def naam_sleutel(desc: str) -> str:
    """'Stuk Boerderijkaas walnoot /kg' en 'Bulk Boerderijkaas walnoot, p/kg' -> 'boerderijkaas walnoot'."""
    d = (desc or "").lower()
    d = re.sub(r"^\s*(stuk|bulk)\b", "", d)
    d = re.sub(r"(,|\s)\s*(p/kg|per kg|/kg|p/st|per stuk)\s*$", "", d)
    return re.sub(r"[^a-z0-9]+", " ", d).strip()


def bulk_items(re_df: pd.DataFrame, regels: Regels, soort: str = "vlees") -> pd.DataFrame:
    """Bulk-items: SKU begint met 2024700, naam begint met 'Bulk'; kaas = afdeling met 'kaas'."""
    kaas_afd = re_df.Inv_DepartID.str.contains("kaas", case=False)
    wil_kaas = regels.soorten[soort].get("bulk_afdeling_bevat_kaas", False)
    b = re_df[
        re_df.Inv_Sku.str.startswith(regels.bulk_sku_prefix)
        & re_df.Inv_Desc.str.match(BULK_NAAM)
        & (kaas_afd if wil_kaas else ~kaas_afd)
    ].copy()
    b["part_nr"] = b.Inv_Part_Vendor.fillna("").str.strip()
    return b


def _klasse(c: str) -> str:
    return (c or "").strip()[:4]


@dataclass
class Koppelresultaat:
    soort: str
    plus: pd.DataFrame                     # een rij per PLU
    bulks: pd.DataFrame                    # alle bulk-items van deze soort
    dubbele_part_nrs: dict[str, list[str]] = field(default_factory=dict)
    niet_in_re: pd.DataFrame | None = None  # weegschaal-PLU's zonder RE-item
    bulks_zonder_plu: pd.DataFrame | None = None

    @property
    def aantal(self) -> int:
        return len(self.plus)

    @property
    def gekoppeld(self) -> int:
        return int(self.plus.bulk_sku.ne("").sum()) if self.aantal else 0

    @property
    def open(self) -> int:
        return self.aantal - self.gekoppeld


def koppel(weegschaal: pd.DataFrame, re_df: pd.DataFrame, regels: Regels, soort: str = "vlees") -> Koppelresultaat:
    instel = regels.soorten[soort]
    bulks = bulk_items(re_df, regels, soort)
    sleutels: dict[str, list[str]] = {}
    for sku, pv in zip(bulks.Inv_Sku, bulks.part_nr):
        if pv:
            sleutels.setdefault(pv.lower(), []).append(sku)
    dubbel = {k: v for k, v in sleutels.items() if len(v) > 1}
    namen: dict[str, list[str]] = {}
    if instel.get("naam_koppeling"):
        for sku, desc in zip(bulks.Inv_Sku, bulks.Inv_Desc):
            namen.setdefault(naam_sleutel(desc), []).append(sku)

    genegeerd = weegschaal[weegschaal.PLU.isin(regels.negeren)]
    w = weegschaal[~weegschaal.PLU.isin(regels.test_plus) & ~weegschaal.PLU.isin(regels.negeren)].copy()
    w["artnr"] = w.PLU.map(plu_naar_artnr)
    w["in_re"] = w.artnr.isin(re_df.index)
    is_kaas = w.Leverancier.isin(regels.kaas_leveranciers)
    van_soort = is_kaas if soort == "kaas" else ~is_kaas
    niet_in_re = w[~w.in_re & van_soort][["PLU", "Artikel", "Leverancier", "Bestelnummer"]].reset_index(drop=True)

    w = w[w.in_re].copy()
    w["klasse"] = w.artnr.map(lambda s: _klasse(re_df.at[s, "Inv_ClassID"]))
    w = w[w.klasse.isin(instel["klassen"])].copy()

    rijen = []
    for r in w.itertuples(index=False):
        item = re_df.loc[r.artnr]
        pv = (item.Inv_Part_Vendor or "").strip()
        bulk_sku, hoe = "", ("geen" if pv else "part nr leeg")
        for naam, k in (("exact", pv.lower()), ("nummer", _voor_komma(pv)), ("tekst", _na_komma(pv))):
            if k and k in sleutels:
                bulk_sku, hoe = sleutels[k][0], naam
                break
        if not bulk_sku and namen:
            kand = namen.get(naam_sleutel(item.Inv_Desc), [])
            if len(kand) == 1:
                bulk_sku, hoe = kand[0], "naam"
        rij = {
            "soort": soort,
            "PLU": int(r.PLU),
            "artnr": r.artnr,
            "omschrijving": re.sub(r"\s+", " ", item.Inv_Desc).strip(),
            "re_leverancier": item.Inv_VendorID,
            "re_part_nr": pv,
            "re_afdeling": item.Inv_DepartID,
            "re_klasse": item.Inv_ClassID,
            "weeg_leverancier": r.Leverancier,
            "weeg_bestelnr": r.Bestelnummer,
            "bulk_sku": bulk_sku,
            "koppeling": hoe,
        }
        if bulk_sku:
            b = bulks.loc[bulk_sku]
            rij.update(bulk_omschrijving=b.Inv_Desc, bulk_leverancier=b.Inv_VendorID,
                       bulk_part_nr=b.part_nr, bulk_klasse=b.Inv_ClassID)
        else:
            rij.update(bulk_omschrijving="", bulk_leverancier="", bulk_part_nr="", bulk_klasse="")
        rij["meldingen"] = "; ".join(_controles(rij, regels))
        rijen.append(rij)

    plus = pd.DataFrame(rijen)
    if not plus.empty:
        per_bulk = plus[plus.bulk_sku.ne("")].groupby("bulk_sku").size()
        plus["plu_per_bulk"] = plus.bulk_sku.map(per_bulk).fillna(0).astype(int)
        gebruikt = set(plus.bulk_sku)
    else:
        gebruikt = set()
    # bulks van genegeerde PLU's (zelfde naam) niet als 'bulk zonder PLU' melden
    genegeerde_namen = {naam_sleutel(a) for a in genegeerd.Artikel}
    zonder = bulks[~bulks.Inv_Sku.isin(gebruikt) & ~bulks.Inv_Desc.map(naam_sleutel).isin(genegeerde_namen)]
    zonder = zonder[["Inv_Sku", "Inv_Desc", "Inv_VendorID", "part_nr"]].reset_index(drop=True)
    return Koppelresultaat(soort=soort, plus=plus, bulks=bulks, dubbele_part_nrs=dubbel,
                           niet_in_re=niet_in_re, bulks_zonder_plu=zonder)


def _controles(rij: dict, regels: Regels) -> list[str]:
    """Meldingen per PLU. Leeg = alles in orde."""
    m: list[str] = []
    plu = rij["PLU"]
    if not rij["bulk_sku"]:
        m.append("Geen bulk: " + regels.open_redenen.get(plu, "leveranciers-artikelnr ontbreekt of geen bulk-item"))
    if plu in regels.samengesteld:
        m.append("Samengesteld artikel (meerdere bulkbronnen): buiten correctie, controleer")
    if rij["koppeling"] == "naam":
        if not rij["re_part_nr"] and not rij["bulk_part_nr"]:
            m.append("Gekoppeld op naam, part nr leeg op retail en bulk: leveranciersnummer invullen (eigen productie: RE-artikelnummer)")
        else:
            m.append(f"Gekoppeld op naam, part nr retail {rij['re_part_nr'] or '(leeg)'} vs bulk "
                     f"{rij['bulk_part_nr'] or '(leeg)'}: gelijk maken")
    # weegschaal-bestelnummer tegen RE (met bekende correcties)
    corr = regels.weegschaal_correcties.get(plu)
    weeg = rij["weeg_bestelnr"]
    re_nr = _voor_komma(rij["re_part_nr"]) if rij["re_part_nr"] else ""
    if corr:
        if weeg != corr["bestelnummer"]:
            m.append(f"Weegschaal corrigeren: bestelnr {weeg or '(leeg)'} moet {corr['bestelnummer']} zijn")
    elif weeg and re_nr and any(c.isdigit() for c in weeg) and weeg.lower() != re_nr:
        # alleen echte nummers vergelijken; tekst als 'Flanksteak' of 'samengesteld' is geen fout
        m.append(f"Bestelnr weegschaal {weeg} wijkt af van RE part nr {rij['re_part_nr']}")
    # leverancier weegschaal tegen RE (ONE TIME negeren)
    verwacht = regels.leveranciers_weegschaal_naar_re.get(rij["weeg_leverancier"])
    if verwacht and verwacht != "ONE TIME" and rij["re_leverancier"] not in ("ONE TIME", verwacht):
        m.append(f"Leverancier weegschaal {rij['weeg_leverancier']} vs RE {rij['re_leverancier']}")
    # klasse retail tegen bulk
    if (rij["bulk_sku"] and plu not in regels.klasse_afwijking_ok
            and _klasse(rij["re_klasse"]) != _klasse(rij["bulk_klasse"])):
        m.append(f"Klasse retail {rij['re_klasse']} vs bulk {rij['bulk_klasse']}")
    return m
