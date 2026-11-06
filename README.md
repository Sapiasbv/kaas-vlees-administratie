# Kaas & Vlees administratie

Voorraad- en koppeladministratie voor kaas, vlees en vleeswaren (Sapias / Bondigro, Bonaire): RetailEdge, weegschaal en PICS-import op één lijn.

Huidige scope: vlees en vleeswaren. Kaas werkt al met het PICS-tool en wordt later meegenomen.

## Installeren (eenmalig)

```
python -m pip install --user -r requirements.txt
```

Zet de bronbestanden in `data/` (zie `docs/HANDOVER.md` §7). Waar de app zoekt staat in `config/instellingen.toml`; bij een patroon met `*` pakt hij het nieuwste bestand.

## Gebruik

Koppelcontrole en mappingtabel Vlees:

```
python administratie.py mapping
```

Resultaat: `uitvoer/Vlees_mappingtabel_<datum>.xlsx` met de tabbladen Uitleg (tellingen), Vlees (nieuw) (zelfde kolommen als het PICS-tool), Actielijst, Niet in RE en Verschil met PICS-tool.

PICS-import uit een of meer Z-afslagen:

```
python administratie.py pics "pad\naar\Artikelen_van_....XLS"
```

- Rekent precies zoals de macro in `Genereer_PICS_import.xlsm` (getest: zelfde uitvoer).
- Standaard mapping: het PICS-tool uit de config (tabbladen Vlees en Kaas). Andere mapping: `--mapping uitvoer\Vlees_mappingtabel_<datum>.xlsx`.
- Extra controles: totaal tegen de totaalregel van de afslag, PLU's zonder bulk, negatieve hoeveelheden, SKU's die niet in RE staan.
- Weigert een afslag die al eerder verwerkt is (logboek `uitvoer/verwerkte_afslagen.csv`); forceren met `--opnieuw`.
- Bestaande bestanden worden nooit overschreven.

In RetailEdge: PICS Import als "Generic CSV - Sku, Quan", daarna PICS Update met **"Append (Add to) Quantities"** (nooit Overwrite).

## Mappen

- `src/kva/`: de applicatie (`bronnen` inlezen, `koppeling` koppelcontrole, `mappingtabel`, `pics`).
- `tests/`: tests met verzonnen voorbeelddata (`python -m pytest`).
- `config/`: regels (`mapping_rules.json`) en paden (`instellingen.toml`).
- `docs/HANDOVER.md`: volledige overdracht.
- `legacy_scripts/`: scripts uit de eerste fase (referentie).
- `data/`, `uitvoer/`: bedrijfsdata, niet in git.

GitHub: `Sapiasbv/kaas-vlees-administratie` (privé, nog aan te maken).
