"""Bestanden opslaan zonder te overschrijven, en het logboek van verwerkte Z-afslagen."""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

from .instellingen import BronFout

LOG_NAAM = "verwerkte_afslagen.csv"


def vrije_naam(pad: Path) -> Path:
    if not pad.exists():
        return pad
    for i in range(2, 1000):
        p = pad.with_name(f"{pad.stem}_v{i}{pad.suffix}")
        if not p.exists():
            return p
    raise BronFout(f"Geen vrije bestandsnaam voor {pad}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lees_log(map_: Path) -> dict[str, dict]:
    p = map_ / LOG_NAAM
    if not p.exists():
        return {}
    with open(p, encoding="utf-8", newline="") as f:
        return {r["sha256"]: r for r in csv.DictReader(f, delimiter=";")}


def schrijf_log(map_: Path, bron_naam: str, hash_: str, uit: Path) -> None:
    p = map_ / LOG_NAAM
    nieuw = not p.exists()
    with open(p, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if nieuw:
            w.writerow(["datum", "bestand", "sha256", "uitvoer"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), bron_naam, hash_, str(uit)])
