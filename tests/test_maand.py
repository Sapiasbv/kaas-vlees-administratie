import dataclasses
from datetime import date

import pandas as pd
import pytest
from openpyxl import Workbook

from kva.instellingen import laad_regels
from kva.koppeling import koppel
from kva.maand import controleer_dekking, lees_re_verkoop, periode_uit_naam, vergelijk


@pytest.fixture
def regels():
    r = laad_regels()
    return dataclasses.replace(r, negeren={}, afslag_indeling={**r.afslag_indeling, "per_stuk": {}})


def verkoop_xlsx(pad):
    wb = Workbook()
    for rij in [
        ["203001", "kg  @ $25.00/kg  Biefstuk, p/kg", "9.5", "100", "237.5", "$137.50", "0.0%", "57.9%", "0.3%"],
        ["203002", "lb  @ $16.39/lb (MAN WT)  Varkensfilet rollade met een hele", "2", "20", "32.78", "$12.78", "0.0%", "39%", "0.1%"],
        [None, "lange naam, p/kg", None, None, None, None, None, None, None],
        ["203003", "lb  @ $6.55/lb  Ossenworst Vers Per stuk", "14", "42", "91.7", "$49.70", "0.0%", "54.2%", "0.1%"],
        ["2024700000335", "MM Purified Water, 16.9oz", "6328", "1455.44", "1825.97", "$370.53", "0%", "20%", "2%"],
    ]:
        wb.active.append(rij)
    wb.save(pad)
    return pad


def test_lees_re_verkoop(tmp_path):
    v = lees_re_verkoop(verkoop_xlsx(tmp_path / "v.xlsx")).set_index("SKU")
    assert len(v) == 4
    assert v.at["203002", "Omschrijving RE"] == "Varkensfilet rollade met een hele lange naam, p/kg"
    assert bool(v.at["203002", "Handmatig gewogen"]) and not bool(v.at["203001", "Handmatig gewogen"])
    assert (v.at["203001", "Verkocht"], v.at["203001", "Omzet"], v.at["203002", "Prijs RE"]) == (9.5, 237.5, 16.39)


def test_vergelijk(tmp_path, regels):
    v = lees_re_verkoop(verkoop_xlsx(tmp_path / "v.xlsx"))
    kol = ["Inv_Sku", "Inv_Desc", "Inv_VendorID", "Inv_Part_Vendor", "Inv_DepartID", "Inv_ClassID"]
    re_df = pd.DataFrame([["203001", "Biefstuk", "VAN KOOTEN", "", "02. Slagerij vers", "0202: Rund"],
                          ["203002", "Rollade", "VAN KOOTEN", "", "02. Slagerij vers", "0203: Varkensvlees"],
                          ["203003", "Ossenworst, p/st", "VAN KOOTEN", "", "03. Vleeswaren", "0301: Vleeswaren"]],
                         columns=kol)
    re_df["Loc_Settings_LocID"] = "Main"
    re_df = re_df.set_index("Inv_Sku", drop=False)
    w = pd.DataFrame([[3001, "Biefstuk", "Van Kooten", ""], [3002, "Rollade", "Van Kooten", ""],
                      [3003, "Ossenworst", "Van Kooten", ""]], columns=["PLU", "Artikel", "Leverancier", "Bestelnummer"])
    ks = [koppel(w, re_df, regels, "vlees"), koppel(w, re_df, regels, "kaas")]
    z = pd.DataFrame([["W", "Van Kooten", "3001", "Rundvlees", "Biefstuk", None, "10"],
                      ["W", "Van Kooten", "3002", "Varkensvlees", "Rollade", None, "2.02"],
                      ["W", "Van Kooten", "3003", "Vleeswaren", "Ossenworst", "16", None],
                      ["Totaal", None, None, None, None, "16", "12.02"]],
                     columns=["Winkel", "Leverancier", "Artikel", "Subgroep omschrijving", "Omschrijving1", "Aantallen", "Gewicht"],
                     dtype=str)
    c = vergelijk([z], v, ks, regels, re_df).tabel.set_index("PLU")
    assert c.at[3001, "Verschil"] == 0.5 and c.at[3001, "Status"] == "OK"       # 5% en 0,5 kg
    assert c.at[3002, "Status"] == "OK"
    assert (c.at[3003, "Eenheid"], c.at[3003, "Verschil"]) == ("st", 2.0)
    assert c.at[3003, "Status"] == "Minder verkocht dan geproduceerd"
    assert c.at[3003, "Waarde verschil (verkoop)"] == pytest.approx(13.1)


def test_periode_en_dekking():
    a = periode_uit_naam("Artikelen_van_20261026_tm_20261101.XLS")
    b = periode_uit_naam("Artikelen_van_20261102_tm_20261108.XLS")
    assert a == (date(2026, 10, 26), date(2026, 11, 1))
    assert controleer_dekking([a, b], date(2026, 10, 26), date(2026, 11, 8)) == []
    assert controleer_dekking([a], date(2026, 10, 30), date(2026, 11, 6))
    assert any("Gat" in m for m in controleer_dekking([a, (date(2026, 11, 5), date(2026, 11, 8))], a[0], date(2026, 11, 8)))
