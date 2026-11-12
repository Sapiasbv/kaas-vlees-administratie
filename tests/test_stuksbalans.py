from datetime import datetime

import pandas as pd

from kva.stuksbalans import (BETER, BLIJFT_OK, MIN, NIEUW, NONSTOCK, OK, PLUS, RECHT, SLECHTER,
                             beoordeel, bewaar_stand, lees_standen)


def stand(rijen):
    df = pd.DataFrame(rijen, columns=["SKU", "Eenheid", "Voorraad", "Stocktype"])
    df["Soort"], df["PLU"], df["Omschrijving"], df["Kostprijs"], df["Gekoppeld"] = "Vlees", 1, "x", 10.0, ""
    df["Waarde"] = df.Voorraad * 10
    return df


def test_status_en_trend(tmp_path):
    week1 = stand([["a", "kg", -3.0, "Stock"], ["b", "kg", 2.0, "Stock"], ["c", "st", 1.0, "Stock"],
                   ["d", "kg", 1.0, "Stock"], ["e", "kg", 5.0, "NonStock"], ["f", "kg", 0.2, "Stock"]])
    t1 = datetime(2026, 11, 9, 8, 0)
    assert bewaar_stand(tmp_path, "export1.csv", t1, week1)
    assert not bewaar_stand(tmp_path, "export1.csv", t1, week1)  # zelfde export niet dubbel
    b1 = beoordeel(week1, lees_standen(tmp_path), t1).tabel.set_index("SKU")
    assert b1.at["a", "Status"] == MIN and b1.at["b", "Status"] == PLUS and b1.at["c", "Status"] == OK
    assert b1.at["e", "Status"] == NONSTOCK and b1.at["a", "Trend"] == NIEUW

    week2 = stand([["a", "kg", 0.1, "Stock"], ["b", "kg", 1.0, "Stock"], ["c", "st", 1.0, "Stock"],
                   ["d", "kg", 4.0, "Stock"], ["e", "kg", 5.0, "NonStock"], ["f", "kg", 0.1, "Stock"]])
    t2 = datetime(2026, 11, 16, 8, 0)
    b2 = beoordeel(week2, lees_standen(tmp_path), t2)
    t = b2.tabel.set_index("SKU")
    assert b2.vorige == t1
    assert t.at["a", "Trend"] == RECHT and t.at["c", "Trend"] == BLIJFT_OK
    assert t.at["b", "Trend"] == BETER and t.at["d", "Trend"] == SLECHTER
    assert t.at["d", "Verandering"] == 3.0
    assert b2.rechtgetrokken == 1
