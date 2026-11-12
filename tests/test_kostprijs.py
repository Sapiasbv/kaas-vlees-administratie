import dataclasses

import pandas as pd

from kva.instellingen import laad_regels
from kva.koppeling import Koppelresultaat
from kva.kostprijs import AANPASSEN, portie_kostprijzen, wijzigingen


def test_portie_gelijk_aan_bulk():
    regels = dataclasses.replace(laad_regels(), samengesteld=frozenset({3612}))
    re_df = pd.DataFrame({"Inv_Cost_Last": {
        "2024700000001": "7.62", "2024700000002": "7.04", "2024700000003": "0.00", "2024700000004": "4.00",
        "203501": "6.54", "203646": "7.62", "203050": "0.70", "203612": "0", "203999": "1", "203517": "5.10"}})
    plus = pd.DataFrame([
        [3501, "203501", "Kipfilet Vers, p/kg", "2024700000001"],
        [3646, "203646", "Kipgehakt", "2024700000001"],
        [3050, "203050", "Rolladeschijf, p/st", "2024700000002"],
        [3612, "203612", "Biefreepjes", "2024700000003"],
        [3999, "203999", "Zonder kost", "2024700000003"],
        [3517, "203517", "Gegrilde hele kip, p/st", "2024700000004"],
    ], columns=["PLU", "artnr", "omschrijving", "bulk_sku"])
    plus["bulk_omschrijving"] = "Bulk"
    t = portie_kostprijzen(re_df, [Koppelresultaat("vlees", plus, pd.DataFrame())], regels).set_index("PLU")
    assert t.at[3501, "Kost nieuw"] == 7.62 and t.at[3501, "Status"] == AANPASSEN
    assert t.at[3646, "Status"] == "OK"
    assert t.at[3050, "Kost nieuw"] == 1.056 and t.at[3050, "Status"].startswith(AANPASSEN)
    assert t.at[3612, "Status"].startswith("Overgeslagen: samengesteld")
    assert t.at[3999, "Status"].startswith("Overgeslagen: bulk")
    assert t.at[3517, "Status"].startswith("Controleren")
    w = {x.sku: x.velden for x in wijzigingen(t.reset_index())}
    assert w == {"203501": {"Inv_Cost_Last": 7.62}, "203050": {"Inv_Cost_Last": 1.056}}
