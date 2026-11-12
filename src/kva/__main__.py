"""Opdrachtregel: python administratie.py <opdracht>

  mapping                 koppelcontrole + mappingtabel Vlees (Excel in de uitvoermap)
  pics BESTAND [...]      PICS-import-CSV maken uit een of meer Z-afslagen
  kostprijs               RE-import: kostprijs porties gelijk aan hun bulk
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .bronnen import lees_mappingtabel, lees_re_export, lees_weegschaal, lees_z_afslag
from .instellingen import BronFout, laad_instellingen, laad_regels, uitvoermap, zoek_bestand
from .koppeling import koppel
from .opslag import lees_log, schrijf_log, sha256, vrije_naam
from .mappingtabel import maak_mappingtabel, schrijf_werkboek
from .pics import maak_pics_import, schrijf_pics_csv

def opdracht_mapping(args, inst, regels) -> int:
    bronnen = {
        "RE-export": zoek_bestand(args.re_export or inst["bronnen"]["re_export"]),
        "Weegschaal-lijst": zoek_bestand(args.weegschaal or inst["bronnen"]["weegschaal"]),
    }
    re_df = lees_re_export(bronnen["RE-export"], regels)
    weeg = lees_weegschaal(bronnen["Weegschaal-lijst"])
    tool = None
    try:
        bronnen["PICS-tool (vergelijking)"] = zoek_bestand(inst["bronnen"]["pics_tool"])
        tool = lees_mappingtabel(bronnen["PICS-tool (vergelijking)"], regels.pics_menu_tabblad)
    except BronFout as e:
        print(f"Let op: geen vergelijking met het PICS-tool ({e})")
    resultaten = []
    for soort in ("vlees", "kaas"):
        k = koppel(weeg, re_df, regels, soort)
        resultaten.append((k, maak_mappingtabel(k, regels)))
    uit = vrije_naam(uitvoermap(inst) / f"Mappingtabel_kaas_vlees_{datetime.now():%Y_%m_%d}.xlsx")
    schrijf_werkboek(uit, resultaten, bronnen, tool)
    for naam, p in bronnen.items():
        print(f"{naam}: {p.name}")
    for k, _ in resultaten:
        print(f"{k.soort.capitalize()}: {k.aantal} PLU's in RE | gekoppeld {k.gekoppeld} | open {k.open} | "
              f"bulk-items {len(k.bulks)} (zonder PLU {len(k.bulks_zonder_plu)}) | dubbele part nrs {len(k.dubbele_part_nrs)} | "
              f"weegschaal niet in RE {len(k.niet_in_re)}")
    print(f"Klaar: {uit}")
    return 0


def opdracht_pics(args, inst, regels) -> int:
    mapping_pad = zoek_bestand(args.mapping or inst["bronnen"]["pics_tool"])
    mapping = lees_mappingtabel(mapping_pad, regels.pics_menu_tabblad)
    print(f"Mappingtabel: {mapping_pad.name} (tabbladen: {', '.join(mapping.tabbladen)}; {len(mapping.regels)} PLU's)")
    for m in mapping.meldingen:
        print(f"  Let op: {m}")
    re_skus = None
    try:
        re_skus = set(lees_re_export(zoek_bestand(inst["bronnen"]["re_export"]), regels).index)
    except BronFout as e:
        print(f"Let op: SKU's niet gecontroleerd tegen RE ({e})")

    map_ = uitvoermap(inst)
    log = lees_log(map_)
    fouten = 0
    for b in args.bestanden:
        bron = Path(b).resolve()
        print()
        try:
            if not bron.is_file():
                raise BronFout(f"Bestand niet gevonden: {bron}")
            h = sha256(bron.read_bytes())
            if h in log and not args.opnieuw:
                eerder = log[h]
                raise BronFout(
                    f"{bron.name} is al verwerkt op {eerder['datum']} ({eerder['uitvoer']}). "
                    "Twee keer importeren boekt de voorraad dubbel. Gebruik --opnieuw als dit echt de bedoeling is.")
            res = maak_pics_import(lees_z_afslag(bron), mapping, bron, re_skus)
            doelmap = bron.parent if args.naast_bron else map_
            uit = vrije_naam(doelmap / f"{bron.stem}_PICS_import.csv")
            schrijf_pics_csv(res, uit)
            schrijf_log(map_, bron.name, h, uit)
            print(res.samenvatting())
            print(f"-> {uit}")
        except BronFout as e:
            fouten += 1
            print(f"[{bron.name}] FOUT: {e}")
    print("\nIn RetailEdge: PICS Import als 'Generic CSV - Sku, Quan', daarna PICS Update met "
          "'Append (Add to) Quantities' (nooit Overwrite).")
    return 1 if fouten else 0


def opdracht_kostprijs(args, inst, regels) -> int:
    from .kostprijs import AANPASSEN, portie_kostprijzen, wijzigingen
    from .re_import import schrijf, template_koppen

    re_pad = zoek_bestand(args.re_export or inst["bronnen"]["re_export"])
    w_pad = zoek_bestand(inst["bronnen"]["weegschaal"])
    template = zoek_bestand(inst["bronnen"].get("re_template", "data/templates/RetailEdge_CSV_Inventory_Import_Template*.xlsx"))
    re_df = lees_re_export(re_pad, regels)
    weeg = lees_weegschaal(w_pad)
    ks = [koppel(weeg, re_df, regels, s) for s in ("vlees", "kaas")]
    tabel = portie_kostprijzen(re_df, ks, regels)
    w = wijzigingen(tabel)
    print(f"RE-export: {re_pad.name} | weegschaal: {w_pad.name}")
    for k in ks:
        t = tabel[tabel.Soort == k.soort]
        print(f"{k.soort.capitalize()}: {k.gekoppeld} gekoppelde porties | gelijk {int(t.Status.str.startswith('OK').sum())} | "
              f"aanpassen {int(t.Status.str.startswith(AANPASSEN).sum())} | "
              f"niet aangepast {int((~t.Status.str.startswith(('OK', AANPASSEN))).sum())}")
    for r in tabel[~tabel.Status.str.startswith(("OK", AANPASSEN))].itertuples(index=False):
        print(f"  {r.PLU} {r.Omschrijving}: {r.Status}")
    if not w:
        print("Niets aan te passen.")
        return 0
    uit = vrije_naam(uitvoermap(inst) / "kostprijs" / f"RE_import_kostprijs_porties_{datetime.now():%Y_%m_%d}.xlsx")
    toel = ["Kostprijs porties = kostprijs bulk",
            f"Bron: {re_pad.name} (locatie Main), {w_pad.name}. Template: {template.name}.",
            "Waste zit één keer in de bulk (besteltool). Portie = bulk; stuksartikel = bulk x kg per stuk.",
            "Alleen Inv_Cost_Last verandert (geel); alle andere kolommen komen uit de huidige RE-export.",
            "Importeren: het CSV-bestand '_bijwerken.csv' in RetailEdge (Inventory Import, bijwerken).",
            f"Aantal: {len(w)} porties. Tabblad 'Alle porties' toont ook wat gelijk is of is overgeslagen."]
    xlsx, csv_pad = schrijf(uit, template_koppen(template), re_df, w, [], toel)
    from openpyxl import load_workbook
    wb = load_workbook(xlsx)
    ws = wb.create_sheet("Alle porties")
    ws.append(list(tabel.columns))
    for r in tabel.itertuples(index=False):
        ws.append(list(r))
    wb.save(xlsx)
    print(f"-> {xlsx}")
    print(f"-> {csv_pad}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kva", description="Kaas & Vlees administratie")
    ap.add_argument("--versie", action="version", version=f"kva {__version__}")
    sub = ap.add_subparsers(dest="opdracht", required=True)

    m = sub.add_parser("mapping", help="koppelcontrole en mappingtabellen Vlees en Kaas maken")
    m.add_argument("--re-export", help="pad naar RE-export (standaard: nieuwste in config)")
    m.add_argument("--weegschaal", help="pad naar weegschaal-lijst (standaard: nieuwste in config)")

    p = sub.add_parser("pics", help="PICS-import maken uit Z-afslag(en)")
    p.add_argument("bestanden", nargs="+", help="Z-afslag(en): .xls, .xlsx of .csv")
    p.add_argument("--mapping", help="mappingtabel (standaard: PICS-tool uit config)")
    p.add_argument("--naast-bron", action="store_true", help="CSV naast de Z-afslag zetten in plaats van in de uitvoermap")
    p.add_argument("--opnieuw", action="store_true", help="ook verwerken als deze afslag al eerder verwerkt is")

    kp = sub.add_parser("kostprijs", help="RE-import: kostprijs porties gelijk aan hun bulk")
    kp.add_argument("--re-export", help="pad naar RE-export (standaard: nieuwste in config)")

    args = ap.parse_args(argv)
    try:
        inst, regels = laad_instellingen(), laad_regels()
        if args.opdracht == "mapping":
            return opdracht_mapping(args, inst, regels)
        if args.opdracht == "kostprijs":
            return opdracht_kostprijs(args, inst, regels)
        return opdracht_pics(args, inst, regels)
    except BronFout as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
