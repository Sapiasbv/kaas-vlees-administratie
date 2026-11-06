"""Instellingen en regels inlezen uit de map config/."""

from __future__ import annotations

import glob
import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECTMAP = Path(__file__).resolve().parents[2]


class BronFout(Exception):
    """Fout in een bronbestand of instelling, met een melding voor de gebruiker."""


@dataclass(frozen=True)
class Regels:
    soorten: dict[str, dict]
    bulk_sku_prefix: str
    test_plus: frozenset[int]
    kaas_leveranciers: frozenset[str]
    afslag_indeling: dict
    samengesteld: frozenset[int]
    controleer_part_nr: frozenset[int]
    open_redenen: dict[int, str]
    negeren: dict[int, str]
    weegschaal_correcties: dict[int, dict]
    leveranciers_weegschaal_naar_re: dict[str, str]
    re_encoding: str
    hoofdlocatie: str
    pics_menu_tabblad: str

    @property
    def leveranciers_re_naar_weegschaal(self) -> dict[str, str]:
        terug: dict[str, str] = {}
        for weeg, re_naam in self.leveranciers_weegschaal_naar_re.items():
            terug.setdefault(re_naam, weeg)
        return terug


def laad_regels(pad: Path | None = None) -> Regels:
    pad = pad or PROJECTMAP / "config" / "mapping_rules.json"
    with open(pad, encoding="utf-8") as f:
        r = json.load(f)
    return Regels(
        soorten=r["soorten"],
        bulk_sku_prefix=r["bulk_sku_prefix"],
        test_plus=frozenset(r.get("test_plus", [])),
        kaas_leveranciers=frozenset(r.get("kaas_leveranciers_weegschaal", [])),
        afslag_indeling=r.get("afslag_indeling", {}),
        samengesteld=frozenset(r.get("samengestelde_artikelen", [])),
        controleer_part_nr=frozenset(r.get("controleer_part_nr", [])),
        open_redenen={int(k): v for k, v in r.get("open_redenen", {}).items()},
        negeren={int(k): v for k, v in r.get("negeren_plus", {}).items()},
        weegschaal_correcties={int(k): v for k, v in r.get("weegschaal_correcties", {}).items()},
        leveranciers_weegschaal_naar_re=r["vendor_map_weegschaal_to_RE"],
        re_encoding=r.get("re_export_encoding", "cp1252"),
        hoofdlocatie=r.get("main_location", "Main"),
        pics_menu_tabblad=r.get("pics_tool_menu_tabblad", "PICS import"),
    )


def laad_instellingen(pad: Path | None = None) -> dict:
    pad = pad or PROJECTMAP / "config" / "instellingen.toml"
    with open(pad, "rb") as f:
        return tomllib.load(f)


def zoek_bestand(patroon: str) -> Path:
    """Geef het bestand bij een pad of patroon; bij een patroon het nieuwste bestand."""
    p = Path(os.path.expandvars(patroon))
    if not p.is_absolute():
        p = PROJECTMAP / p
    if any(t in str(p) for t in "*?["):
        kandidaten = [Path(x) for x in glob.glob(str(p)) if Path(x).is_file()]
        if not kandidaten:
            raise BronFout(f"Geen bestand gevonden voor patroon: {p}")
        return max(kandidaten, key=lambda x: x.stat().st_mtime)
    if not p.is_file():
        raise BronFout(f"Bestand niet gevonden: {p}")
    return p


def uitvoermap(instellingen: dict) -> Path:
    p = Path(instellingen.get("uitvoer", {}).get("map", "uitvoer"))
    if not p.is_absolute():
        p = PROJECTMAP / p
    p.mkdir(parents=True, exist_ok=True)
    return p
