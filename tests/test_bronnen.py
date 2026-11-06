import pytest
from openpyxl import Workbook

from kva.bronnen import lees_weegschaal


def schrijf(pad, rijen):
    wb = Workbook()
    for r in rijen:
        wb.active.append(r)
    wb.save(pad)
    return pad


@pytest.mark.parametrize("rijen", [
    # oude indeling (t/m 4-11-2026): leverancier in kolom C, code in G
    [[3011, "Serranoham, p/kg", "Van Kooten", 2145, None, None, 15180, "25,08"],
     [3026, "Iberico diepvries, p/kg", None, None, None, None, None, "32,16"]],
    # nieuwe indeling (6-11-2026): groepnummer in kolom C
    [[3011, "Serranoham, p/kg", 6, "Van Kooten", 2145, 15180, "25,08"],
     [3026, "Iberico diepvries, p/kg", None, None, None, None, "32,16"]],
    # ruwe export (6-11-2026, 21 kolommen): PLU in kolom B, groepnaam ertussen, extra kolommen erachter
    [[None, 3011, "Serranoham, p/kg", None, 6, "Vleeswaren", None, None, "Van Kooten", 2145, None, None, 15180,
      "25,08", "Btw 0.00 % (3)", "0.6154", "18-03-2026", None, None, 7, "X"],
     [None, 3026, "Iberico diepvries, p/kg", None, 6, "Vleeswaren", None, None, None, None, None, None, None,
      "32,16", "Btw 0.00 % (3)", None, None, None, None, 7, "X"]],
])
def test_weegschaal_beide_indelingen(tmp_path, rijen):
    w = lees_weegschaal(schrijf(tmp_path / "w.xlsx", rijen))
    r = w.set_index("PLU").loc[3011]
    assert (r.Leverancier, r.Bestelnummer, str(r.Weegschaalcode), r.Prijs) == ("Van Kooten", "2145", "15180", "25,08")
    assert w.set_index("PLU").at[3026, "Leverancier"] == ""
