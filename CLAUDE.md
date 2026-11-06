# CLAUDE.md

Project: vlees-administratie voor Sapias / Bondigro (Bonaire). Lees eerst `docs/HANDOVER.md`.

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
- `legacy_scripts/` zijn werkende scripts uit de Cowork-sessie. Ze verwijzen naar oude paden (`/tmp/claude-0/...`, `/root/.claude/uploads/...`) en moeten worden herschreven naar `src/` met paden uit een configuratie.

## Verificatie
Controleer elk resultaat met een telling tegen de bron (aantal PLU's, aantal bulk-items, aantal gekoppeld) en laat die tellingen aan de gebruiker zien.
