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
3. **PICS-lijst maken**: controle tegen RE, met een overzicht per bulk (wat eraf gaat, op welke porties het erbij komt, en of dat sluit). Daarna opslaan in `uitvoer/` (plus een Excel met de regels en het overzicht per bulk) en downloaden.
4. **Importeren in RetailEdge** volgens de SOP (Append, nooit Overwrite).

Voorblad: wat er deze week moet gebeuren (verse RE-export, Z-afslag, NonStock-porties) en de **stuksbalans**: na een correctie hoort elke portie rond 0 te staan (productie erbij, verkoop eraf). De app waarschuwt bij porties in de plus of min (drempel en datum van de nulmeting in `config/instellingen.toml`, `[stuksbalans]`). Elke RE-export wordt per portie bewaard in `Uitvoer app\stuksbalans\standen.csv`; zo is te zien of een afwijking de week erna is rechtgetrokken.

Pagina **Voorraad & tellijsten**: bulk- en stuksvoorraad, stuksbalans volgens de RE-export (bekijken en als Excel downloaden), tellijsten uitdraaien (`uitvoer/tellijsten/`, vast formaat: tabblad Info, Tellijst bulk/stuks, verborgen tabblad Systeem met de voorraad bij uitdraaien) en een ingevulde tellijst weer inlezen voor de telverschillen.

Pagina **Maandcontrole**: productie weegschaal (Z-afslagen) tegen verkoop RetailEdge, per PLU, over dezelfde periode. RE-rapport: Reports > *Sales by Items - Grouped by Location*, presets *Summary Report* en *Department only*, opslaan als *Excel File - Data (\*.xls)*. Geen kopregel: A SKU, B item, C aantal/kg, D kost, E omzet, F marge, G korting, H marge %, I aandeel. "lb" in kolom B is alleen een label; de hoeveelheid is kg.

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
- `data/`, `uitvoer/`: bedrijfsdata, niet in git (oude werkmappen; sinds 8-11-2026 staat het werk op de gedeelde schijf).

## Gedeelde schijf (sinds 8-11-2026)

`%USERPROFILE%\OneDrive - SAPIAS\Share-BDG-General - Documents\Slagerij en kaas administratie`:

- `RE-export\`: inventory export (locatie Main, afdelingen 02, 03, 04, 13, 14). De app pakt de nieuwste.
- `Weegschaal-lijst\`: weegschaal item-overzicht (elke opmaak). De app pakt de nieuwste.
- `Z-afslagen\`: de weekafslagen (kies je in stap 1).
- `PICS_import_tool\`: het oude tool van Nick (alleen gelezen, voor de kaas-aanvulling).
- `Uitvoer app\`: PICS-lijsten, `_verwerking.xlsx`, logboek `verwerkte_afslagen.csv`, `afslagen\` (archief), `tellijsten\`, `maandcontrole\`.

Het logboek bevat ook de weken die nog via het PICS-tool zijn gedaan (t/m 26-10 t/m 1-11-2026), zodat de app waarschuwt bij dubbel verwerken. Paden staan in `config/instellingen.toml`.

GitHub: `Sapiasbv/kaas-vlees-administratie` (privé).
