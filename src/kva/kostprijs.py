"""Kostprijs van de porties gelijk aan hun bulk (besluit Sjors 12-11-2026).

De waste (vlees 5%) zit één keer in de kostprijs van de bulk (besteltool). Tussen bulk en portie komt
er niets bij: portie = bulk-kostprijs, bij stuksartikelen maal het gewicht per stuk (per_stuk in
mapping_rules.json; 'stuk' = de bulk telt ook per stuk, factor 1).

Niet aangepast: samengestelde artikelen, bulks zonder kostprijs, en stuksartikelen ('p/st' in de naam)
waarvan het gewicht per stuk niet bekend is.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pandas as pd

from .bronnen import getal
from .instellingen import Regels
from .koppeling import Koppelresultaat
from .re_import import Wijziging

KOLOMMEN = ["Soort", "PLU", "SKU", "Omschrijving", "Bulk SKU", "Bulk", "Factor", "Kost bulk", "Kost nu",
            "Kost nieuw", "Verschil %", "Status"]
PER_STUK_NAAM = re.compile(r"(?i)\bp\.?/?\s*st\b|per stuk")
AANPASSEN = "Aanpassen"


def _factor(plu: int, naam: str, regels: Regels) -> tuple[Decimal | None, str]:
    w = regels.afslag_indeling.get("per_stuk", {}).get(str(plu))
    if w == "stuk":
        return Decimal(1), "per stuk (bulk ook per stuk)"
    if w is not None:
        return Decimal(str(w)), f"{w} kg per stuk"
    if PER_STUK_NAAM.search(naam or ""):
        return None, ""
    return Decimal(1), ""


def portie_kostprijzen(re_df: pd.DataFrame, koppelingen: list[Koppelresultaat], regels: Regels,
                       drempel_pct: float = 0.5) -> pd.DataFrame:
    """Een regel per gekoppelde portie. Status 'Aanpassen' als de kostprijs meer dan drempel_pct afwijkt."""
    rijen = []
    for k in koppelingen:
        if k.plus.empty:
            continue
        for p in k.plus[k.plus.bulk_sku.ne("")].itertuples(index=False):
            nu = getal(re_df.at[p.artnr, "Inv_Cost_Last"])
            bulk = getal(re_df.at[p.bulk_sku, "Inv_Cost_Last"])
            factor, uitleg = _factor(p.PLU, p.omschrijving, regels)
            nieuw, verschil = None, None
            if p.PLU in regels.samengesteld:
                status = "Overgeslagen: samengesteld artikel"
            elif not bulk:
                status = "Overgeslagen: bulk heeft geen kostprijs"
            elif factor is None:
                status = "Controleren: per stuk, gewicht per stuk onbekend"
            else:
                nieuw = (bulk * factor).quantize(Decimal("0.0001"))
                verschil = None if not nu else float((nu / nieuw - 1) * 100)
                gelijk = nu and abs(nu - nieuw) <= nieuw * Decimal(str(drempel_pct)) / 100
                status = "OK" if gelijk else AANPASSEN
                if uitleg:
                    status += f" ({uitleg})"
            rijen.append({
                "Soort": k.soort, "PLU": int(p.PLU), "SKU": p.artnr, "Omschrijving": p.omschrijving,
                "Bulk SKU": p.bulk_sku, "Bulk": p.bulk_omschrijving,
                "Factor": None if factor is None else float(factor),
                "Kost bulk": None if bulk is None else float(bulk),
                "Kost nu": None if nu is None else float(nu),
                "Kost nieuw": None if nieuw is None else float(nieuw),
                "Verschil %": None if verschil is None else round(verschil, 1),
                "Status": status,
            })
    return pd.DataFrame(rijen, columns=KOLOMMEN)


def wijzigingen(tabel: pd.DataFrame) -> list[Wijziging]:
    """RE-import: alleen Inv_Cost_Last verandert; de rest neemt re_import over uit de export."""
    t = tabel[tabel.Status.str.startswith(AANPASSEN)]
    uit = []
    for r in t.to_dict("records"):
        reden = f"Kostprijs = bulk {r['Bulk SKU']} ({r['Kost bulk']:.4f})"
        if r["Factor"] != 1:
            reden += f" x {r['Factor']:g} kg per stuk"
        uit.append(Wijziging(sku=r["SKU"], velden={"Inv_Cost_Last": r["Kost nieuw"]}, reden=reden))
    return uit
