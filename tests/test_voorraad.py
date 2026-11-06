import dataclasses

import pandas as pd
import pytest
from openpyxl import load_workbook

from kva.instellingen import BronFout, laad_regels
from kva.koppeling import koppel
from kva.voorraad import lees_tellijst, maak_tellijst, telverschillen, voorraad_lijst


@pytest.fixture
def regels():
    r = laad_regels()
    return dataclasses.replace(r, negeren={}, afslag_indeling={**r.afslag_indeling, "per_stuk": {"3029": "stuk"}})


def re_export():
    kol = ["Inv_Sku", "Inv_Desc", "Inv_VendorID", "Inv_Part_Vendor", "Inv_DepartID", "Inv_ClassID", "Inv_Quan", "Inv_Cost_Last"]
    df = pd.DataFrame([
        ["2024700000001", "Bulk 2145, Serranoham", "VAN KOOTEN", "2145", "02. Slagerij vers", "0203: Varkensvlees", "10.5", "15.18"],
        ["2024700000002", "Bulk 99, Ossenworst", "VAN KOOTEN", "99", "03. Vleeswaren", "0301: Vleeswaren", "-4", "3.00"],
        ["203011", "Serranoham, p/kg", "VAN KOOTEN", "2145, Serranoham", "02. Slagerij vers", "0203: Varkensvlees", "2.25", "15.18"],
        ["203029", "Ossenworst, p/st", "VAN KOOTEN", "99, Ossenworst", "03. Vleeswaren", "0301: Vleeswaren", "3", "3.00"],
    ], columns=kol)
    df["Loc_Settings_LocID"] = "Main"
    return df.set_index("Inv_Sku", drop=False)


def test_lijst_tellijst_en_verschillen(tmp_path, regels):
    re_df = re_export()
    w = pd.DataFrame([[3011, "Serranoham", "Van Kooten", "2145"], [3029, "Ossenworst", "Van Kooten", "99"]],
                     columns=["PLU", "Artikel", "Leverancier", "Bestelnummer"])
    lijst = voorraad_lijst(re_df, [koppel(w, re_df, regels, "vlees")], regels)
    assert list(lijst.Type) == ["Bulk", "Bulk", "Stuk", "Stuk"]
    eenheid = dict(zip(lijst.SKU, lijst.Eenheid))
    assert eenheid == {"2024700000001": "kg", "2024700000002": "st", "203011": "kg", "203029": "st"}
    assert lijst.set_index("SKU").at["2024700000001", "Waarde"] == pytest.approx(159.39)

    pad = maak_tellijst(lijst, tmp_path / "tel.xlsx", "test.csv")
    wb = load_workbook(pad)
    assert wb.sheetnames == ["Info", "Tellijst bulk", "Tellijst stuks", "Systeem"]
    assert wb["Systeem"].sheet_state == "hidden"
    ws = wb["Tellijst bulk"]
    kop = [c.value for c in ws[4]]
    assert "Systeem" not in kop  # blind tellen
    g = kop.index("Geteld") + 1
    ws.cell(5, g, 9)       # bulk Serranoham (alfabetisch na Ossenworst? nee: afdeling 02 eerst)
    ws.cell(6, g, "-4")    # Ossenworst klopt
    wb["Tellijst stuks"].cell(5, g, "2,5")
    wb.save(pad)

    t = lees_tellijst(pad)
    assert len(t.geteld) == 3 and t.niet_geteld == 1
    v = telverschillen(t, re_df).set_index("SKU")
    assert v.at["2024700000001", "Verschil"] == pytest.approx(-1.5)
    assert v.at["2024700000001", "Waarde verschil"] == pytest.approx(-22.77)
    assert v.at["2024700000002", "Verschil"] == 0
    assert v.at["203011", "Verschil"] == pytest.approx(0.25)


def test_geen_tellijst(tmp_path):
    from openpyxl import Workbook
    Workbook().save(tmp_path / "x.xlsx")
    with pytest.raises(BronFout):
        lees_tellijst(tmp_path / "x.xlsx")
