from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from kva.bronnen import Mapping, MappingRegel, lees_mappingtabel
from kva.pics import formatteer, maak_pics_import, schrijf_pics_csv


def mapping(*regels):
    m = Mapping(tabbladen=["Vlees"])
    for plu, art, bulk in regels:
        m.regels[plu] = MappingRegel(plu, art, bulk, "Vlees", 2)
    return m


def afslag(rijen):
    return pd.DataFrame(rijen, columns=["Winkel", "Artikel", "Omschrijving1", "Aantallen", "Gewicht"], dtype=str)


@pytest.mark.parametrize("v,uit", [
    ("9.224", "9.224"), ("14.67", "14.67"), ("9", "9"), ("1.0005", "1.001"),
    ("-1.0005", "-1.001"), ("0.0001", "0"), ("-0.0001", "0"), ("303.4670000000001", "303.467"),
])
def test_formatteer(v, uit):
    assert formatteer(Decimal(v)) == uit


def test_zoals_macro_porties_dan_bulks_en_optellen():
    m = mapping((1, "200001", "2024700000001"), (2, "200002", "2024700000001"), (3, "200003", ""))
    z = afslag([
        ["W", "1", "a", None, "1.5"],
        ["W", "2", "b", None, "2.25"],
        ["W", "1", "a", None, "0.5"],
        ["W", "3", "c", None, "4"],
        ["Totaal", None, None, "0", "8.25"],
        ["In % excl derving", "0", None, None, None],
    ])
    r = maak_pics_import(z, m, Path("x.xls"))
    assert r.regels_csv() == ["200001,2", "200002,2.25", "200003,4", "2024700000001,-4.25"]
    assert r.zonder_bulk == {3: "c"}
    assert r.totaal_afslag == Decimal("8.25")
    assert "-> OK" in r.samenvatting()


def test_aantallen_gaat_voor_gewicht_en_lege_regels_overslaan():
    m = mapping((1, "200001", "B1"), (2, "200002", "B2"))
    z = afslag([
        ["W", "1", "stuks", "3", "0.9"],
        ["W", "2", "leeg", None, None],
        ["W", "2", "nul", "0", "0"],
        ["", "1", "geen winkel", None, "5"],
    ])
    r = maak_pics_import(z, m, Path("x.xls"))
    assert r.regels_csv() == ["200001,3", "B1,-3"]
    assert set(r.geen_hoeveelheid) == {2}


def test_onbekende_plu_en_negatief_en_re_controle():
    m = mapping((1, "200001", "2024700000001"))
    z = afslag([["W", "1", "retour", None, "-1"], ["W", "77", "onbekend", None, "2"], ["Totaal", None, None, None, "1"]])
    r = maak_pics_import(z, m, Path("x.xls"), re_skus={"200001"})
    assert r.niet_gevonden == {77: "onbekend"}
    assert r.negatief == {1: Decimal("-1")}
    assert r.re_onbekend == ["2024700000001"]
    assert "-> OK" in r.samenvatting()  # -1 + 2 = 1


def test_schrijf_csv_crlf_en_niet_overschrijven(tmp_path):
    r = maak_pics_import(afslag([["W", "1", "a", None, "1"]]), mapping((1, "200001", "B")), Path("x.xls"))
    p = schrijf_pics_csv(r, tmp_path / "uit.csv")
    assert p.read_bytes() == b"200001,1\r\nB,-1\r\n"
    with pytest.raises(FileExistsError):
        schrijf_pics_csv(r, p)


def test_lees_mappingtabel_zoals_tool(tmp_path):
    wb = Workbook()
    menu = wb.active
    menu.title = "PICS import"
    menu.append(["menu"])
    for naam, rijen in {
        "Vlees": [[3001, 203001, 2024700092606], [3002, 203002, "n.v.t. (zelfde artikel)"], ["tekst", 1, 1]],
        "Kaas": [[1004, 201004, 2024700100356.0], [3001, 203001, 2024700000009]],
        "Uitleg": None,
    }.items():
        ws = wb.create_sheet(naam)
        if rijen is None:
            ws.append(["vrije tekst"])
            continue
        ws.append(["Type", "Portie PLU *", "Portie ART NR *", "Bulk SKU (RetailEdge) *"])
        for plu, art, bulk in rijen:
            ws.append(["x", plu, art, bulk])
    pad = tmp_path / "tool.xlsx"
    wb.save(pad)
    m = lees_mappingtabel(pad)
    assert m.tabbladen == ["Vlees", "Kaas"]
    assert m.regels[3002].bulk_sku == ""
    assert m.regels[1004].bulk_sku == "2024700100356"
    assert m.regels[3001].tabblad == "Kaas"  # laatste wint, zoals de macro
    assert any("dubbel" in x for x in m.meldingen)
    assert any("geen getal" in x for x in m.meldingen)
