# CLAUDE.md

Project: Kaas & Vlees administratie voor Sapias / Bondigro (Bonaire). Huidige scope: vlees en vleeswaren; kaas werkt al met het PICS-tool en komt later. Lees eerst `docs/HANDOVER.md`.

## Locaties
- Projectmap: `C:\Claude\Kaas & Vlees administratie`.
- Gedeelde schijf (kaas-tool en Z-afslagen): `C:\Users\BonaireHospitalitySu\OneDrive - SAPIAS\Share-BDG-General - Documents\Slagerij en kaas administratie`.
- Eerdere opleveringen: `C:\Users\BonaireHospitalitySu\OneDrive - SAPIAS\Desktop\Claude\Vlees administratie`.

## Werkafspraken
- Taal: Nederlands. Antwoorden kort, feitelijk, met cijfers. Geen gokwerk tenzij gevraagd. Sarcasme is welkom.
- Vraag bij twijfel, vooral bij nummers (leveranciersnummers, SKU's, prijzen).
- Verzin nooit bulk-SKU's. De gebruiker maakt die zelf aan in RetailEdge.
- Wijzig nooit bestaande bedrijfsbestanden op de gedeelde schijf zonder opdracht. Schrijf resultaten als nieuw bestand ernaast.
- RE-import van bestaande items: neem alle huidige kolomwaarden over en verander alleen wat nodig is.
- Commit geen bedrijfsdata (zie `.gitignore`): exports, facturen, pakbonnen, Excel-bestanden blijven in `data/`.

## Technische afspraken
- RE-export is cp1252. Lees alles als tekst (`dtype=str`) en zet getallen pas daarna om.
- Z-afslag is `.XLS`: `xlrd` nodig. Weegschaal-lijst en templates zijn `.xlsx` (openpyxl).
- `.xlsm` met macro's niet met openpyxl opslaan (VBA gaat verloren). Gebruik directe OOXML-aanpassing of lever een los bestand.
- Regels en mappings staan in `config/mapping_rules.json`.
- De applicatie staat in `src/kva/` (Python). Starten: `python administratie.py mapping` of `python administratie.py pics <afslag>`. Paden in `config/instellingen.toml`.
- PICS-uitvoer moet gelijk blijven aan de macro in `Genereer_PICS_import.xlsm` (Aantallen voor Gewicht, porties eerst, 3 decimalen). Draai `python -m pytest` na elke wijziging.
- `legacy_scripts/` zijn de oude Cowork-scripts (alleen referentie; oude paden).

## Verificatie
Controleer elk resultaat met een telling tegen de bron (aantal PLU's, aantal bulk-items, aantal gekoppeld) en laat die tellingen aan de gebruiker zien.
