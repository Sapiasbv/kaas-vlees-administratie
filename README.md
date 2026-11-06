# Kaas & Vlees administratie

Voorraad- en koppeladministratie voor kaas, vlees en vleeswaren (Sapias / Bondigro, Bonaire): RetailEdge, weegschaal en PICS-import op één lijn.

Scope: vlees, vleeswaren en kaas. Let op: verwerk een afslag die via deze app gaat niet ook nog in het oude PICS-tool (dan wordt kaas dubbel geboekt).

## Installeren (eenmalig)

```
python -m pip install --user -r requirements.txt
```

Zet de bronbestanden in `data/` (zie `docs/HANDOVER.md` §7). Waar de app zoekt staat in `config/instellingen.toml`; bij een patroon met `*` pakt hij het nieuwste bestand.

## Scherm (wekelijkse voorraadcorrectie)

Dubbelklik `start_scherm.cmd`. De browser opent op http://localhost:8501 (alleen op deze computer). Stappen:

1. **Upload de Z-afslag** van afgelopen week (maandag t/m zondag), de export van de hele weegschaal. De app controleert de periode en of deze afslag al verwerkt is.
2. **Check bijzonderheden**: elke regel wordt ingedeeld als Vlees, Kaas (elk met of zonder bulk), Buiten scope (fruit, bake-off) of Onbekend. Totaalcontrole in kg en stuks tegen de totaalregel. Aanpassen kan: meenemen, hoeveelheid, portie ART NR, bulk SKU en hoeveel kg er van de bulk afgaat (nodig bij stuksartikelen).
3. **PICS-lijst maken**: controle tegen RE, daarna opslaan in `uitvoer/` (plus een Excel met de verwerkte regels) en downloaden.
4. **Importeren in RetailEdge** volgens de SOP (Append, nooit Overwrite).

De mapping voor vlees en kaas komt rechtstreeks uit de RE-export en weegschaal-lijst (zelfde koppelregels als `mapping`: part nr, en anders naam 'Stuk/… X' = 'Bulk X'). Kaas-PLU's die daar ontbreken maar in het Kaas-tabblad van het PICS-tool staan, worden aangevuld.

## Opdrachtregel

Koppelcontrole en mappingtabellen Vlees en Kaas:

```
python administratie.py mapping
```

Resultaat: `uitvoer/Mappingtabel_kaas_vlees_<datum>.xlsx` met de tabbladen Uitleg (tellingen), Vlees (nieuw), Kaas (nieuw) (zelfde kolommen als het PICS-tool), Actielijst en Verschil met PICS-tool.

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
