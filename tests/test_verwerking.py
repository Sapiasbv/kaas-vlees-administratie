from datetime import date

import pandas as pd
import pytest

from kva.bronnen import Mapping, MappingRegel
from kva.instellingen import laad_regels
from kva.verwerking import (
    BUITEN, KAAS, ONBEKEND, VLEES, VLEES_GEEN_BULK, controleer_periode, deel_in, pics_regels, totaalcontrole,
)


@pytest.fixture
def regels():
    return laad_regels()


def mp(*rijen, tab="Vlees"):
    m = Mapping(tabbladen=[tab])
    for plu, art, bulk in rijen:
        m.regels[plu] = MappingRegel(plu, art, bulk, tab, 2)
    return m


def afslag(rijen):
    kol = ["Winkel", "Leverancier", "Artikel", "Subgroep omschrijving", "Omschrijving1", "Aantallen", "Gewicht"]
    return pd.DataFrame(rijen, columns=kol, dtype=str)


Z = afslag([
    ["W", "Van Kooten", "3001", "Rundvlees", "Biefstuk", None, "2.5"],
    ["W", "Van Kooten", "3029", "Vleeswaren", "Ossenworst per stuk", "4", None],
    ["W", "One time", "3027", "Vleeswaren", "Pastrami", None, "1"],
    ["W", "Van Beek ZV", "1007", "Kaas", "Kaas walnoot", None, "3"],
    ["W", None, "1410", None, "Kaas Hotelblok", None, "0.5"],
    ["W", None, "1410", None, "Geitenkaas", None, "0.25"],
    ["W", "DIFS", "2502", "Overig", "Appeltaart", "5", None],
    ["W", "Van Kooten", "3521", "Gevogelte", "Kip hele poot", None, "7"],
    ["Totaal", None, None, None, None, "9", "14.25"],
    ["In % excl derving", None, "0", None, None, None, None],
])


def test_indeling_en_totaal(regels):
    vlees = mp((3001, "203001", "2024700000001"), (3029, "203029", "2024700000002"), (3027, "203027", ""))
    kaas = mp((1007, "201007", "2024700100363"), tab="Kaas")
    re_df = pd.DataFrame(index=["203001", "203029", "203027", "201007", "2024700000001", "2024700000002"])
    ind = deel_in(Z, vlees, kaas, regels, re_df)
    t = ind.tabel.set_index("Omschrijving")
    assert t.Categorie.to_dict() == {
        "Biefstuk": VLEES, "Ossenworst per stuk": VLEES, "Pastrami": VLEES_GEEN_BULK, "Kaas walnoot": KAAS,
        "Kaas Hotelblok": KAAS, "Geitenkaas": KAAS, "Appeltaart": BUITEN, "Kip hele poot": ONBEKEND}
    assert t.Meenemen.to_dict()["Kaas walnoot"] is False  # kaas via PICS-tool
    assert t.at["Ossenworst per stuk", "Eenheid"] == "st"
    assert "Per stuk" in t.at["Ossenworst per stuk", "Melding"]
    assert "niet (meer) in RE" in t.at["Kip hele poot", "Melding"]
    assert "meerdere keren" in t.at["Geitenkaas", "Melding"]
    assert all(ok for _, ok, _ in totaalcontrole(ind))


def test_pics_regels_met_aanpassing(regels):
    vlees = mp((3001, "203001", "2024700000001"), (3029, "203029", "2024700000001"), (3027, "203027", ""))
    t = deel_in(Z, vlees, None, regels).tabel
    i = t.index[t.PLU == 3029][0]
    t.at[i, "Bulk afboeken"] = 1.2  # 4 stuks = 1,2 kg
    lijst = pics_regels(t)
    assert lijst.fouten == []
    assert lijst.regels == ["203001,2.5", "203029,4", "203027,1", "2024700000001,-3.7"]


def test_pics_regels_fouten(regels):
    t = deel_in(Z, mp((3001, "203001", "2024700000001")), None, regels).tabel
    i = t.index[t.PLU == 3521][0]
    t.at[i, "Meenemen"] = True
    t.at[i, "Portie ART NR"] = ""
    lijst = pics_regels(t, re_skus={"203001", "2024700000001"})
    assert any("3521" in f for f in lijst.fouten)


@pytest.mark.parametrize("naam,aantal_meldingen", [
    ("Artikelen_van_20261026_tm_20261101.XLS", 0),
    ("Artikelen_van_20261027_tm_20261101.XLS", 2),  # dinsdag, 6 dagen
    ("onbekend.xls", 1),
])
def test_periode(naam, aantal_meldingen):
    p = controleer_periode(naam, vandaag=date(2026, 11, 6))
    assert len(p.meldingen) == aantal_meldingen
