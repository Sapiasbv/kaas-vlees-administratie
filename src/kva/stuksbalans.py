"""Stuksbalans: staan de porties (stuks-items) na de Z-afslag-correctie rond 0?

In theorie wordt elke week verkocht wat er is geproduceerd: de PICS-lijst zet de productie erbij, RetailEdge
haalt de verkoop eraf, en de voorraad van een portie blijft rond 0. In de praktijk ontstaan er verschillen.

- Stand: de voorraad van elke portie volgens de RE-export (Inv_Quan).
- Historie: elke RE-export die de app inleest, wordt per portie bewaard (stuksbalans/standen.csv).
  Daarmee is te zien of een afwijking de week erna weer is rechtgetrokken door de verkoop.
- NonStock: RetailEdge houdt dan geen voorraad bij; de stand zegt dan niets.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from .voorraad import STUK

STANDEN = "standen.csv"
DREMPEL = {"kg": 0.5, "st": 2.0}

OK = "OK"
PLUS = "Plus (te veel)"
MIN = "Min (te weinig)"
NONSTOCK = "NonStock in RE"

RECHT = "Rechtgetrokken"
BETER = "Beter"
SLECHTER = "Slechter"
GELIJK = "Gelijk"
NIEUW = "Eerste meting"
BLIJFT_OK = "Blijft OK"


@dataclass
class Balans:
    tabel: pd.DataFrame
    stand: datetime
    vorige: datetime | None

    def aantal(self, status: str) -> int:
        return int((self.tabel.Status == status).sum())

    @property
    def gemeten(self) -> pd.DataFrame:
        return self.tabel[self.tabel.Status != NONSTOCK]

    def som(self, status: str, eenheid: str) -> float:
        t = self.tabel
        return float(t.loc[(t.Status == status) & (t.Eenheid == eenheid), "Voorraad"].sum())

    def waarde(self, status: str) -> float:
        return float(self.tabel.loc[self.tabel.Status == status, "Waarde"].sum())

    @property
    def rechtgetrokken(self) -> int:
        return int((self.tabel.Trend == RECHT).sum())


def stuks_stand(lijst: pd.DataFrame, re_df: pd.DataFrame) -> pd.DataFrame:
    """Porties uit de voorraadlijst, met de stocktype uit RE."""
    s = lijst[lijst.Type == STUK].copy()
    s["Stocktype"] = s.SKU.map(re_df.Inv_StockType).fillna("")
    return s[["Soort", "SKU", "PLU", "Omschrijving", "Eenheid", "Voorraad", "Kostprijs", "Waarde", "Gekoppeld", "Stocktype"]]


def bewaar_stand(map_: Path, bron: str, tijd: datetime, stand: pd.DataFrame) -> bool:
    """Voeg de stand toe aan de historie (een keer per RE-export). Geeft True als hij nieuw was."""
    map_.mkdir(parents=True, exist_ok=True)
    p = map_ / STANDEN
    sleutel = tijd.strftime("%Y-%m-%d %H:%M")
    if p.exists():
        oud = pd.read_csv(p, sep=";", dtype=str)
        if ((oud.Stand == sleutel) & (oud.Bron == bron)).any():
            return False
    nieuw = not p.exists()
    with open(p, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if nieuw:
            w.writerow(["Stand", "Bron", "SKU", "Voorraad", "Stocktype"])
        for r in stand.itertuples(index=False):
            w.writerow([sleutel, bron, r.SKU, f"{r.Voorraad:.3f}", r.Stocktype])
    return True


def lees_standen(map_: Path) -> pd.DataFrame:
    p = map_ / STANDEN
    if not p.exists():
        return pd.DataFrame(columns=["Stand", "Bron", "SKU", "Voorraad", "Stocktype"])
    df = pd.read_csv(p, sep=";", dtype=str, keep_default_na=False)
    df["Voorraad"] = pd.to_numeric(df.Voorraad, errors="coerce")
    df["Stand"] = pd.to_datetime(df.Stand)
    return df


def _status(q: float, eenheid: str, stocktype: str, drempel: dict) -> str:
    if stocktype and stocktype.lower() != "stock":
        return NONSTOCK
    if abs(q) <= drempel.get(eenheid, 0.5):
        return OK
    return PLUS if q > 0 else MIN


def beoordeel(stand: pd.DataFrame, standen: pd.DataFrame, tijd: datetime, drempel: dict | None = None) -> Balans:
    """Status per portie en de trend tegen de vorige meting (de laatste stand van vóór deze export)."""
    drempel = drempel or DREMPEL
    t = stand.copy()
    t["Status"] = [_status(q, e, s, drempel) for q, e, s in zip(t.Voorraad, t.Eenheid, t.Stocktype)]
    eerder = standen[standen.Stand < pd.Timestamp(tijd).floor("min")]
    vorige = None
    if not eerder.empty:
        vorige = eerder.Stand.max()
        v = eerder[eerder.Stand == vorige].drop_duplicates("SKU", keep="last").set_index("SKU")
        t["Vorige stand"] = t.SKU.map(v.Voorraad)
        t["Vorige stocktype"] = t.SKU.map(v.Stocktype).fillna("")
    else:
        t["Vorige stand"] = float("nan")
        t["Vorige stocktype"] = ""
    trends = []
    for r in t.itertuples(index=False):
        if pd.isna(r[t.columns.get_loc("Vorige stand")]) or r.Status == NONSTOCK:
            trends.append(NIEUW if r.Status != NONSTOCK else "")
            continue
        oud = r[t.columns.get_loc("Vorige stand")]
        oud_status = _status(oud, r.Eenheid, r[t.columns.get_loc("Vorige stocktype")], drempel)
        d = drempel.get(r.Eenheid, 0.5)
        if r.Status == OK:
            trends.append(BLIJFT_OK if oud_status == OK else RECHT)
        elif abs(r.Voorraad) < abs(oud) - d:
            trends.append(BETER)
        elif abs(r.Voorraad) > abs(oud) + d:
            trends.append(SLECHTER)
        else:
            trends.append(GELIJK)
    t["Trend"] = trends
    t["Verandering"] = (t.Voorraad - t["Vorige stand"]).round(3)
    volgorde = {MIN: 0, PLUS: 1, NONSTOCK: 2, OK: 3}
    t = t.assign(_v=t.Status.map(volgorde), _w=-t.Waarde.abs()).sort_values(["_v", "_w"]).drop(columns=["_v", "_w", "Vorige stocktype"])
    return Balans(tabel=t.reset_index(drop=True), stand=tijd, vorige=None if vorige is None else vorige.to_pydatetime())
