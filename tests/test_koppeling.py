import pandas as pd
import pytest

from kva.instellingen import laad_regels
from kva.koppeling import koppel
from kva.mappingtabel import bulk_artikelnaam, maak_mappingtabel


@pytest.fixture
def regels():
    return laad_regels()


def re_export(items):
    df = pd.DataFrame(items, columns=["Inv_Sku", "Inv_Desc", "Inv_VendorID", "Inv_Part_Vendor", "Inv_DepartID", "Inv_ClassID"])
    df["Loc_Settings_LocID"] = "Main"
    return df.set_index("Inv_Sku", drop=False)


def weegschaal(rijen):
    return pd.DataFrame(rijen, columns=["PLU", "Artikel", "Leverancier", "Bestelnummer"])


def test_koppelregels(regels):
    re_df = re_export([
        ["2024700000001", "Bulk 2145, Serranoham", "VAN KOOTEN", "2145", "02. Slagerij vers", "0203: Varkensvlees"],
        ["2024700000002", "Bulk, Flanksteak", "VAN KOOTEN", "flanksteak p/kg", "02. Slagerij vers", "0202: Rund"],
        ["2024700000003", "Bulk Kaas", "VAN BEEK", "999", "03. Kaas vers gesneden", "0302: Kaas"],
        ["203001", "Serranoham", "VAN KOOTEN", "2145, Serranoham blok", "03. Vleeswaren", "0301: Vleeswaren"],
        ["203002", "Flanksteak", "VAN KOOTEN", ", Flanksteak p/kg", "02. Slagerij vers", "0202: Rund"],
        ["203003", "Pastrami", "ONE TIME", "", "03. Vleeswaren", "0301: Vleeswaren"],
        ["201004", "Kaas", "VAN BEEK ZV", "999", "03. Kaas", "0302: Kaas"],
        ["202400", "Fruit", "EIGEN PRODUCTIE", "", "02. Slagerij vers", "0102 : Fruit"],
    ])
    w = weegschaal([
        [3001, "Serranoham", "Van Kooten", "2145"],
        [3002, "Flanksteak", "Van Kooten", "Flanksteak"],
        [3003, "Pastrami", "One time", ""],
        [1004, "Kaas", "Van Beek ZV", ""],
        [2400, "Fruit", "Eigen productie", ""],
        [3999, "Bestaat niet in RE", "Van Kooten", ""],
        [9999, "Test", "", ""],
    ])
    k = koppel(w, re_df, regels)
    assert len(k.bulks) == 2  # kaas-bulk telt niet mee
    assert dict(zip(k.plus.PLU, k.plus.bulk_sku)) == {3001: "2024700000001", 3002: "2024700000002", 3003: ""}
    assert dict(zip(k.plus.PLU, k.plus.koppeling)) == {3001: "nummer", 3002: "tekst", 3003: "part nr leeg"}
    assert list(k.niet_in_re.PLU) == [3999]
    assert (k.aantal, k.gekoppeld, k.open) == (3, 2, 1)

    tabel = maak_mappingtabel(k, regels)
    assert list(tabel["Portie PLU *"]) == [3001, 3002, 3003]  # open rijen onderaan
    assert list(tabel.Type) == ["1-op-1", "1-op-1", "?"]
    assert tabel.iloc[0]["Bulk art.nr (lev.) *"] == 2145
    assert tabel.iloc[0]["Bulk leverancier *"] == "Van Kooten"


def test_weegschaal_correctie_en_afwijking(regels):
    re_df = re_export([
        ["2024700092675", "Bulk 310006, Kippenborst, bulk", "DELI NOVA", "310006", "02. Slagerij vers", "0201: Kip"],
        ["203508", "Kipshoarma", "DELI NOVA", "310006, Kippenborst, bulk", "02. Slagerij vers", "0201: Kip"],
        ["203509", "Kipsate", "DELI NOVA", "310006, Kippenborst, bulk", "02. Slagerij vers", "0201: Kip"],
    ])
    w = weegschaal([[3508, "Kipshoarma", "Deli Nova", "310007"], [3509, "Kipsate", "Deli Nova", "310099"]])
    k = koppel(w, re_df, regels)
    meld = dict(zip(k.plus.PLU, k.plus.meldingen))
    assert "moet 310006 zijn" in meld[3508]
    assert "wijkt af" in meld[3509]
    assert set(k.plus.plu_per_bulk) == {2}
    assert set(maak_mappingtabel(k, regels).Type) == {"Splitser (2x)"}


@pytest.mark.parametrize("desc,uit", [
    ("Bulk 2098, Buik z/b z/zw", "Buik z/b z/zw"),
    ("Bulk, Kip Cervelaat", "Kip Cervelaat"),
    ("Bulk H6149-0014, Chicken 1300gr", "Chicken 1300gr"),
    ("Bulk 310006, Kippenborst, bulk", "Kippenborst, bulk"),
])
def test_bulk_artikelnaam(desc, uit):
    assert bulk_artikelnaam(desc) == uit
