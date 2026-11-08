"""Mappingtabel Vlees genereren in het formaat van het PICS-tool, plus actielijst."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .bronnen import Mapping
from .instellingen import Regels
from .koppeling import Koppelresultaat

KOLOMMEN = [
    "Type", "Bulk leverancier *", "Bulk art.nr (lev.) *", "Bulk artikel (inkoop) *",
    "Bulk SKU (RetailEdge) *", "Portie PLU *", "Portie ART NR *", "Portie omschrijving *", "Let op",
]
GEEL = PatternFill("solid", fgColor="FFF2CC")
KOP = PatternFill("solid", fgColor="1F3864")


def bulk_artikelnaam(desc: str) -> str:
    """'Bulk 2098, Buik z/b' -> 'Buik z/b'; 'Bulk, Kipfilet' -> 'Kipfilet'."""
    d = re.sub(r"(?i)^\s*bulk\s*", "", desc or "")
    if re.match(r"^[A-Za-z0-9\-]+,", d):
        d = re.sub(r"^[^,]*\d[^,]*,\s*", "", d)
    return d.lstrip(", ").strip()


def maak_mappingtabel(k: Koppelresultaat, regels: Regels) -> pd.DataFrame:
    naar_weeg = regels.leveranciers_re_naar_weegschaal
    if not k.aantal:
        return pd.DataFrame(columns=KOLOMMEN, dtype=object)
    p = k.plus.copy()
    p["_open"] = p.bulk_sku.eq("")
    p = p.sort_values(["_open", "bulk_sku", "PLU"])
    rijen = []
    for r in p.itertuples(index=False):
        if r.bulk_sku:
            n = int(r.plu_per_bulk)
            let = ""
            if r.PLU in regels.samengesteld:
                let = "Samengesteld artikel (eigen productie): meerdere bulkbronnen, buiten correctie. Controleer."
            elif r.PLU in regels.controleer_part_nr:
                let = "Controleer part nr"
            factor = regels.afslag_indeling.get("per_stuk", {}).get(str(r.PLU))
            if factor not in (None, "stuk"):
                let = (f"Per stuk verkocht, bulk in kg: het PICS-tool boekt het aantal stuks als kg af. "
                       f"Moet aantal x {str(factor).replace('.', ',')} kg zijn: bulkregel met de hand corrigeren.")
            pn = r.bulk_part_nr
            rijen.append([
                "1-op-1" if n == 1 else f"Splitser ({n}x)",
                naar_weeg.get(r.bulk_leverancier, r.bulk_leverancier),
                int(pn) if pn.isdigit() else (pn or None),
                bulk_artikelnaam(r.bulk_omschrijving),
                int(r.bulk_sku), r.PLU, int(r.artnr), r.omschrijving, let or None,
            ])
        else:
            reden = regels.open_redenen.get(r.PLU, "Leveranciers-artikelnr ontbreekt: aan te vullen")
            rijen.append(["?", naar_weeg.get(r.re_leverancier, r.re_leverancier), None, None, None,
                          r.PLU, int(r.artnr), r.omschrijving, reden])
    return pd.DataFrame(rijen, columns=KOLOMMEN, dtype=object)


def verschil_met_tool(tabel: pd.DataFrame, tool: Mapping | None, tabblad: str = "Vlees") -> pd.DataFrame:
    kol = ["Portie PLU", "Omschrijving", "PICS-tool: bulk SKU", "Nieuw: bulk SKU", "Wijziging"]
    if tool is None:
        return pd.DataFrame(columns=kol)
    oud = {p: m.bulk_sku for p, m in tool.regels.items() if m.tabblad == tabblad}
    rijen = []
    for r in tabel.itertuples(index=False):
        plu, nieuw = r[5], (str(r[4]) if r[4] is not None else "")
        if plu not in oud:
            rijen.append([plu, r[7], None, nieuw or None, "Nieuw in tabel"])
        elif oud[plu] != nieuw:
            wat = "Krijgt bulk-item" if not oud[plu] else ("Bulk vervalt" if not nieuw else "Ander bulk-item")
            rijen.append([plu, r[7], oud[plu] or None, nieuw or None, wat])
    nieuw_plus = set(tabel["Portie PLU *"])
    for plu in sorted(set(oud) - nieuw_plus):
        rijen.append([plu, None, oud[plu] or None, None, "Uit tabel verwijderen (niet meer in weegschaal-lijst of RE)"])
    return pd.DataFrame(rijen, columns=kol)


def actielijst(k: Koppelresultaat) -> pd.DataFrame:
    rijen = []
    if k.aantal:
        for r in k.plus[k.plus.meldingen.ne("")].sort_values("PLU").itertuples(index=False):
            for m in r.meldingen.split("; "):
                rijen.append([k.soort, r.PLU, r.omschrijving, r.re_part_nr or None, r.weeg_bestelnr or None, m])
    for pv, skus in k.dubbele_part_nrs.items():
        rijen.append([k.soort, None, None, pv, None, f"Dubbel bulk part nr in RE: {', '.join(skus)}"])
    if k.bulks_zonder_plu is not None:
        for b in k.bulks_zonder_plu.itertuples(index=False):
            rijen.append([k.soort, None, b.Inv_Desc, b.part_nr or None, None,
                          f"Bulk {b.Inv_Sku} heeft geen PLU (part nr past bij geen enkele PLU): koppelen of opruimen"])
    for b in k.niet_in_re.itertuples(index=False):
        rijen.append([k.soort, b.PLU, b.Artikel, None, b.Bestelnummer or None,
                      "Staat op de weegschaal maar niet in RE: aanmaken in RE of van de weegschaal halen"])
    return pd.DataFrame(rijen, columns=["Soort", "PLU", "Omschrijving", "RE part nr", "Weegschaal bestelnr", "Actie / melding"])


def _blad(wb: Workbook, titel: str, df: pd.DataFrame, breedtes: list[int], geel=None):
    ws = wb.create_sheet(titel)
    ws.append(list(df.columns))
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = KOP
    for rij in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in rij])
    for j, b in enumerate(breedtes, 1):
        ws.column_dimensions[get_column_letter(j)].width = b
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions
    if geel:
        for rij in ws.iter_rows(min_row=2):
            if geel(rij):
                for c in rij:
                    c.fill = GEEL
    # grote SKU's als getal zonder wetenschappelijke notatie
    for rij in ws.iter_rows(min_row=2):
        for c in rij:
            if isinstance(c.value, int) and c.value > 10**9:
                c.number_format = "0"
    return ws


TABBLAD = {"vlees": "Vlees", "kaas": "Kaas"}


def schrijf_werkboek(pad: Path, resultaten: list[tuple[Koppelresultaat, pd.DataFrame]], bronnen: dict[str, Path],
                     tool: Mapping | None = None) -> Path:
    """Een werkboek met per soort een mappingtabel in PICS-tool-formaat, plus actielijst en verschillen."""
    if pad.exists():
        raise FileExistsError(f"Bestaat al, niet overschreven: {pad}")
    wb = Workbook()
    uitleg = wb.active
    uitleg.title = "Uitleg"
    acties = pd.concat([actielijst(k) for k, _ in resultaten], ignore_index=True)
    verschillen = []
    for k, tabel in resultaten:
        v = verschil_met_tool(tabel, tool, TABBLAD[k.soort])
        v.insert(0, "Soort", k.soort)
        verschillen.append(v)
    verschil = pd.concat(verschillen, ignore_index=True)
    regels = [
        ("Mappingtabellen Vlees en Kaas (voor de tabbladen in Genereer_PICS_import.xlsm)", True),
        (f"Gemaakt op {date.today():%d-%m-%Y} met kva (Kaas & Vlees administratie).", False),
        ("", False),
        ("Bronnen:", True),
        *[(f"  {naam}: {p.name}", False) for naam, p in bronnen.items()],
        ("", False),
        ("Tellingen:", True),
    ]
    for k, _ in resultaten:
        regels += [
            (f"  {TABBLAD[k.soort]}: {k.aantal} PLU's in RE, {k.gekoppeld} gekoppeld, {k.open} zonder bulk; "
             f"{len(k.bulks)} bulk-items, {len(k.bulks_zonder_plu)} zonder PLU, {len(k.dubbele_part_nrs)} dubbele part nrs; "
             f"{len(k.niet_in_re)} weegschaal-PLU's niet in RE", False),
        ]
    regels += [
        (f"  Regels in de actielijst: {len(acties)}", False),
        (f"  Verschillen met het huidige PICS-tool: {len(verschil)}", False),
        ("", False),
        ("Gebruik:", True),
        ("  De tabbladen 'Vlees (nieuw)' en 'Kaas (nieuw)' hebben dezelfde kolommen als het PICS-tool.", False),
        ("  Geel = nog aan te vullen of te controleren (kolom 'Let op').", False),
        ("  Type: 1-op-1 = een bulk voor een PLU; Splitser (nx) = een bulk voor n PLU's.", False),
        ("  Het PICS-tool zelf wordt door dit programma nooit gewijzigd.", False),
    ]
    for i, (t, vet) in enumerate(regels, 1):
        uitleg.cell(i, 1, t).font = Font(bold=vet, size=13 if i == 1 else 11)
    uitleg.column_dimensions["A"].width = 140

    for k, tabel in resultaten:
        _blad(wb, f"{TABBLAD[k.soort]} (nieuw)", tabel, [14, 18, 16, 44, 16, 10, 12, 42, 70],
              geel=lambda rij: rij[0].value == "?" or bool(rij[8].value))
    _blad(wb, "Actielijst", acties, [8, 8, 40, 40, 22, 90])
    _blad(wb, "Verschil met PICS-tool", verschil, [8, 10, 42, 22, 18, 60])
    pad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pad)
    return pad
