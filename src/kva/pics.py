"""PICS-importbestand maken uit een Z-afslag, gelijk aan de macro in Genereer_PICS_import.xlsm.

Per regel in de Z-afslag:
  hoeveelheid = Aantallen (als gevuld en niet 0), anders Gewicht (als gevuld en niet 0), anders overslaan.
  portie-artikel (ART NR)  += hoeveelheid
  bulk-artikel   (SKU)     -= hoeveelheid   (alleen als de PLU een bulk heeft)
Uitvoer: CSV zonder kopregel, 'SKU,hoeveelheid', eerst alle porties, dan alle bulks,
afgerond op 3 decimalen. In RE inlezen als 'Generic CSV - Sku, Quan' en PICS Update met
'Append (Add to) Quantities' (nooit Overwrite).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

from .bronnen import Mapping, getal, tekst

DRIE = Decimal("0.001")


def formatteer(v: Decimal) -> str:
    """Afronden op 3 decimalen (half naar boven, zoals Excel ROUND), zonder overbodige nullen."""
    s = format(v.quantize(DRIE, rounding=ROUND_HALF_UP).normalize(), "f")
    if s in ("-0", "0", ""):
        return "0"
    return s


@dataclass
class PicsResultaat:
    bron: Path
    porties: dict[str, Decimal] = field(default_factory=dict)
    bulks: dict[str, Decimal] = field(default_factory=dict)
    niet_gevonden: dict[int, str] = field(default_factory=dict)
    zonder_bulk: dict[int, str] = field(default_factory=dict)
    geen_hoeveelheid: dict[int, str] = field(default_factory=dict)
    negatief: dict[int, Decimal] = field(default_factory=dict)
    regels_verwerkt: int = 0
    totaal_porties: Decimal = Decimal(0)
    totaal_bulk: Decimal = Decimal(0)
    totaal_afslag: Decimal | None = None
    totaal_niet_gevonden: Decimal = Decimal(0)
    re_onbekend: list[str] = field(default_factory=list)

    def regels_csv(self) -> list[str]:
        return [f"{k},{formatteer(v)}" for k, v in self.porties.items()] + \
               [f"{k},{formatteer(v)}" for k, v in self.bulks.items()]

    def samenvatting(self) -> str:
        r = [
            f"[{self.bron.name}]",
            f"{self.regels_verwerkt} regels verwerkt: {len(self.porties)} portie-artikelen, {len(self.bulks)} bulk-artikelen.",
            f"Totaal bijgeboekt op porties: {formatteer(self.totaal_porties)}; afgeboekt van bulk: {formatteer(-self.totaal_bulk)}.",
        ]
        if self.totaal_afslag is not None:
            som = self.totaal_porties + self.totaal_niet_gevonden
            oordeel = "OK" if formatteer(som) == formatteer(self.totaal_afslag) else                 f"VERSCHIL {formatteer(som - self.totaal_afslag)} (controleer de afslag)"
            r.append(f"Controle: verwerkt {formatteer(self.totaal_porties)} + niet in mapping "
                     f"{formatteer(self.totaal_niet_gevonden)} = {formatteer(som)}; totaalregel Z-afslag "
                     f"{formatteer(self.totaal_afslag)} -> {oordeel}.")
        if self.niet_gevonden:
            r.append(f"LET OP: {len(self.niet_gevonden)} PLU('s) niet in de mappingtabel (niet meegenomen):")
            r += [f"  - PLU {p}: {o}" for p, o in self.niet_gevonden.items()]
        if self.zonder_bulk:
            r.append(f"Info: {len(self.zonder_bulk)} PLU('s) zonder bulk: portie bijgeboekt, geen bulk afgeboekt:")
            r += [f"  - PLU {p}: {o}" for p, o in self.zonder_bulk.items()]
        if self.negatief:
            r.append(f"LET OP: {len(self.negatief)} PLU('s) met negatieve hoeveelheid (retour?):")
            r += [f"  - PLU {p}: {formatteer(v)}" for p, v in self.negatief.items()]
        if self.geen_hoeveelheid:
            r.append(f"Info: {len(self.geen_hoeveelheid)} PLU('s) zonder aantal en gewicht (overgeslagen):")
            r += [f"  - PLU {p}: {o}" for p, o in self.geen_hoeveelheid.items()]
        if self.re_onbekend:
            r.append(f"LET OP: {len(self.re_onbekend)} SKU('s) uit de mapping bestaan niet in de RE-export: {', '.join(self.re_onbekend)}")
        return "\n".join(r)


def maak_pics_import(z: pd.DataFrame, mapping: Mapping, bron: Path, re_skus: set[str] | None = None) -> PicsResultaat:
    res = PicsResultaat(bron=bron)
    omschr_kol = "Omschrijving1" if "Omschrijving1" in z.columns else None
    for rij in z.to_dict("records"):
        winkel = tekst(rij.get("Winkel"))
        if winkel == "Totaal":
            res.totaal_afslag = getal(rij.get("Gewicht"))
        if winkel in ("", "Totaal"):
            continue
        art = getal(rij.get("Artikel"))
        if art is None or art == 0:
            continue
        plu = int(art.to_integral_value(rounding=ROUND_HALF_UP))
        omschr = tekst(rij.get(omschr_kol)) if omschr_kol else ""

        hoeveelheid = None
        for kol in ("Aantallen", "Gewicht"):
            v = getal(rij.get(kol))
            if v is not None and v != 0:
                hoeveelheid = v
                break
        if hoeveelheid is None:
            res.geen_hoeveelheid.setdefault(plu, omschr)
            continue

        m = mapping.regels.get(plu)
        if m is None:
            res.niet_gevonden.setdefault(plu, omschr)
            res.totaal_niet_gevonden += hoeveelheid
            continue
        res.regels_verwerkt += 1
        if hoeveelheid < 0:
            res.negatief[plu] = res.negatief.get(plu, Decimal(0)) + hoeveelheid
        res.porties[m.artnr] = res.porties.get(m.artnr, Decimal(0)) + hoeveelheid
        res.totaal_porties += hoeveelheid
        if m.bulk_sku:
            res.bulks[m.bulk_sku] = res.bulks.get(m.bulk_sku, Decimal(0)) - hoeveelheid
            res.totaal_bulk -= hoeveelheid
        else:
            res.zonder_bulk.setdefault(plu, omschr)

    if re_skus is not None:
        res.re_onbekend = sorted(s for s in [*res.porties, *res.bulks] if s not in re_skus)
    return res


def schrijf_pics_csv(res: PicsResultaat, pad: Path) -> Path:
    if pad.exists():
        raise FileExistsError(f"Bestaat al, niet overschreven: {pad}")
    pad.parent.mkdir(parents=True, exist_ok=True)
    with open(pad, "w", encoding="ascii", newline="\r\n") as f:
        for regel in res.regels_csv():
            f.write(regel + "\n")
    return pad
