# Overdracht: Kaas & Vlees administratie (Sapias / Bondigro, Bonaire)

Stand: 6 november 2026. Opgesteld vanuit een Claude-sessie (Cowork) om het werk voort te zetten in Claude Code.
Alle feiten komen uit de gegevens die in die sessie zijn gebruikt. Controleer cijfers altijd opnieuw tegen een verse export.

## Locaties
- Projectmap (repo): `C:\Claude\Kaas & Vlees administratie`.
- Gedeelde schijf met PICS-tool en Z-afslagen: `...\Share-BDG-General - Documents\Slagerij en kaas administratie`.
- Eerdere opleveringen (Excel-bestanden): `...\OneDrive - SAPIAS\Desktop\Claude\Vlees administratie`.

## 1. Doel

Eén eenvoudige applicatie die de vleesadministratie bijhoudt en RetailEdge (RE) en de weegschaal met elkaar in lijn houdt.
Het moet "dummy-proof" zijn, want alle collega's gebruiken het, en het moet op een gedeelde schijf (SharePoint/OneDrive) werken.

Gebruiker: Sjors (inkoop- en logistiek manager). Taal: Nederlands. Voorkeur: feiten en cijfers, korte antwoorden, sarcasme mag.
Geen aannames zonder bronnen. Vraag bij twijfel.

## 2. Het probleem in het kort

- Vlees komt binnen als **bulk** (hele ham, doos kip) en wordt op de weegschaal versneden tot **PLU-artikelen** die los verkocht worden.
- RE en de weegschaal-software hebben **geen koppeling**. Verkoop wordt alleen op de PLU geboekt, inkoop alleen op de bulk. Zonder correctie loopt de bulkvoorraad op en de PLU-voorraad af.
- Collega's loggen transfer orders (TO) maar niet de inkomende goederen. Facturen en pakbonnen worden handmatig verwerkt (typfouten).
- Voor **kaas** is dit al opgelost met een tool (zie 4). Voor vlees moet dat nog gebeuren.

## 3. Systemen en bestanden

### RetailEdge (RE)
- Inventory-export als CSV, encoding **cp1252**, 57 kolommen. Locatie `Main`. Sleutelvelden: `Inv_Sku`, `Inv_Desc`, `Inv_VendorID`, `Inv_Part_Vendor`, `Inv_DepartID`, `Inv_ClassID`, `Inv_Cost_Last`, `Inv_Loc_Price_Was`, `Inv_Loc_Price1..5`, `Inv_Quan`, `Inv_ItemID`.
- Import-CSV volgt het "RetailEdge CSV Inventory Import Template" (44 kolommen, rode verplichte velden A t/m L). Importeren van bestaande items werkt als update op `Inv_Sku`. Neem dan alle huidige kolomwaarden over, anders worden ze overschreven.
- In de import-CSV heten drie kolommen anders dan in de export: `User Field 4` = `Text on Price Tag`, `CustomSubTotal1` = `EBT`, `CustomSubTotal2` = `DUFB`.
- Boolean-kolommen (`Inv_Loc_Taxable`, `Inv_Loc_DenySales`, `Inv_Cost_Dynamic`, `CustomSubTotal1-3`) als TRUE/FALSE.

### Weegschaal
- **Weegschaal item-overzicht** (leidende lijst, 4-11-2026): kolommen zonder kop: PLU, Artikel, Leverancier, Bestelnummer leverancier, (leeg), (leeg), weegschaalcode, verkoopprijs. 221 regels, inclusief kaas, salades en testregels (9999, 999999).
- **Z-afslag**: XLS-export per periode (`Artikelen_van_<yyyymmdd>_tm_<yyyymmdd>.XLS`). Kolommen: Winkel, Afd, Locatie, Leverancier, Artikel (= PLU), Bestelnr., Subgr., Subgroep omschrijving, Omschrijving1, Omschrijving2, Omzet incl, Btw, Omzet excl, Inkoop, Marge, Perc, Aantallen, Gewicht, BTW %. Lezen met `xlrd`.
- De afslagen sinds september bevatten alleen kaas. Vlees staat alleen in `20260730_tm_20260731` (testperiode). Kolom `Aantallen` is overal leeg. Hoe artikelen per stuk (p/st) in de afslag komen is dus onbekend.

### PICS-tool (kaas, gemaakt met Claude, eigenaar proces: Nick)
- Locatie: `...\Share-BDG-General - Documents\Slagerij en kaas administratie\` met mappen `PICS_import_tool` en `Z-afslagen`.
- `Genereer_PICS_import.xlsm` heeft tabbladen "PICS import" (menu met macro-knoppen), "Vlees" en "Kaas" (mappingtabellen). SOP: `SOP_Voorraadcorrectie_Slagerij_Kaas.pdf` v1.0 (14-8-2026).
- Werking: de macro leest een Z-afslag, zoekt elke PLU in de mappingtabel en schrijft `<Z-afslag>_PICS_import.csv` met twee regels per PLU: `<portie ART NR>,+gewicht` en `<bulk SKU>,-gewicht`. In RE wordt dit ingelezen via PICS Update met **"Append (Add to) Quantities"** (nooit Overwrite).
- Mappingkolommen: Type, Bulk leverancier, Bulk art.nr (lev.), Bulk artikel (inkoop), Bulk SKU (RetailEdge), Portie PLU, Portie ART NR, Portie omschrijving, Let op, Validatie. Types: `1-op-1`, `Splitser (nx)`. Samengestelde artikelen zijn "buiten correctie".
- Het tabblad Vlees is **verouderd** (146 rijen, 22 bulk-items, meeste rijen "1-op-1 zonder bulk"). Een voorstel voor een nieuwe tabel is gemaakt (zie 7).

### Eigen Excel-administratie (eerder in dit project gemaakt)
- `Vlees_Sapias_TO_systeem_1.2.xlsm`: oude opzet met macro, Log, Hoofddata, NEW_STOCK, SUMIF op Log. Bevat 57 gelogde factuurregels (FACT-…).
- `Vlees_Sapias_Voorraad_2.0_eenvoudig.xlsx`: eenvoudige versie (Start hier, Voorraad, Mutaties, Documenten, Koppeling, Lijsten). Sluit aan op de oude (10.543,86 kg).
- Nulmeting: **27-08-2026**. Alleen facturen van na die datum zijn verwerkt, op factuurdatum.

## 4. Datamodel en regels (afspraken met de gebruiker)

- RE-artikelnummer van een PLU = **200000 + PLU** (PLU 3711 → 203711).
- Bulk-SKU: `2024700` + teller + controlecijfer. De gebruiker maakt bulk-SKU's zelf aan in RE (de app mag ze niet verzinnen).
- Bulk-naam: `Bulk <leveranciersnummer>, <omschrijving>`; zonder nummer `Bulk, <omschrijving>`.
- **Koppeling retail → bulk via vendor part nummer.** Bulk heeft alleen het nummer (`2145`). Retail heeft `2145, Serranoham blok varkens`. Match: begint met nummer, of de tekst achter de komma is gelijk. Eigen productie en artikelen zonder leveranciersnummer: RE-artikelnummer als part nr op beide kanten (voorbeeld: `203691`).
- Vendor-mapping weegschaal → RE: zie `config/mapping_rules.json`.
- Afdeling 03. Vleeswaren voor klassen 0301/0303, anders 02. Slagerij vers. Retail-items mogen op 13. Basismand of 14. Hardlopers staan: niet vergelijken met bulk.
- Kostprijs bulk = laatste factuurprijs × factor (parameters: landed 1,5, EUR→USD 1,00, prijsfactor 1,35, alleen als terugval). Prijzen van retail komen uit het hoofd-PLU (laagste PLU met RE-item, liefst niet One time).
- `Inv_Loc_Taxable` altijd FALSE.
- Buiten scope: salades, fruit, DIFS, normale Bondigro-SKU's, kaas (eigen proces). Genegeerd: leverancier **ONE TIME** bij controles, patés (tijdelijk).
- Eenheden: bulk en PLU worden in kg geboekt. Bij p/st-artikelen is dit nog niet vastgesteld.

## 5. Wat is gedaan

1. Facturen sinds de nulmeting verwerkt in beide Excel-versies.
2. RE en de oude lijst "Vlees en vleeswaren assortiment en nummers" opgeschoond tegen de weegschaal-lijst (23 RE-items verwijderd, 6 met voorraad).
3. Import-bestanden gemaakt voor 91 nieuwe bulk-items en daarna voor bijwerken van bestaande items. De gebruiker heeft de bulk-items aangemaakt en de bijwerk-import (5-11-2026) verwerkt.
4. Controle op 4-11-2026: 163 vlees-PLU's in RE, 111 bulk-items. Na de import van 5-11 zijn **148 van 163 PLU's gekoppeld** (gesimuleerd, nog niet met een verse export bevestigd).
5. Pakbon Van Kooten 26766731 (5-11-2026) gebruikt om ontbrekende nummers te vinden (2114, 393, 5034, 2966, 3010, 111, 2210).
6. Het PICS-tool onderzocht en een voorstel voor de nieuwe tabel Vlees gemaakt: 163 rijen (148 met bulk, 15 open).

## 6. Open punten

Data:
- 15 PLU's zonder bulk-koppeling: patés 3121-3126, Pastrami 3027, Rundervink 3644, Sausage links 3043, Kippendij met bot 3562-3564 (Foods USA-nummer onbekend), Prosciutto 3025 (geen bulk), Rolladeschijf 3050 (RE leeg, weegschaal zegt 2098 = Buik).
- 3508 Kipshoarma: weegschaal 310007, RE 310006. Welk nummer klopt?
- Weegschaal-lijst bevat fouten: bestelnr 93 bij 3025 en 3063; leverancier Deelen ZV bij 3641/3651/3652/3682 terwijl RE en bulk Van Kooten zijn; bestelnr 3020 bij Katenspek moet 2114 zijn.
- Weegschaal-PLU's die niet in RE staan: 3120 Lamsbout, 3026 Iberico diepvries, 3217 Kalfs hart zwezerik, 3090/3091 Ham di Pasku (alleen oude items 2024700084939/946 zonder part nr), 2135-2138 Droge Worst (scan-items).
- Bulk `2024700106280` (Bulk, Kip Cervelaat) is dubbel met Bulk 354 en kan uit RE.
- Klasseverschillen retail/bulk (o.a. 203716, 203724, 203645, 203004).
- Nog niet verwerkt: oudere facturen van vóór de nulmeting, 37 factuurartikelen zonder match.

Proces:
- Beslissen of vlees via de Z-afslag verwerkt wordt en hoe p/st-artikelen en `Aantallen` werken. Testen met een echte vlees-afslag.
- Samengestelde artikelen (Gourmetschotel 3101, Biefreepjes 3612/3615, BBQ-pakket 3691) halen uit meerdere bulks: buiten correctie.
- Inkoop automatisch inlezen (pakbon/factuur-PDF's) en TO's, zodat typefouten verdwijnen.

## 7. Eerder opgeleverde bestanden (niet in de repo, staan in de map Vlees administratie)

`Vlees_Sapias_TO_systeem_1.2.xlsm`, `Vlees_Sapias_Voorraad_2.0_eenvoudig.xlsx`, `RE_en_lijst_opschoning_2026_11_04.xlsx`, `RetailEdge_Import_Bulk_en_PLU_2026_11_04.xlsx`, `RetailEdge_Import_Bijwerken_Koppeling_2026_11_05.xlsx`, `Vlees_koppeling_controle_2026_11_04.xlsx`, `Vlees_mappingtabel_voorstel_2026_11_05.xlsx`.
Bronnen die nodig zijn om de scripts te draaien: RE-inventory-export, weegschaal item-overzicht, RE-importtemplate, Z-afslagen, factuur/pakbon-data. Leg die in `data/` (genegeerd door git).

## 8. Voorstel voor de applicatie (nog te bevestigen met de gebruiker)

Onderdelen:
1. **Inlezen**: RE-export, weegschaal-lijst, Z-afslag, pakbon/factuur (PDF).
2. **Koppelcontrole**: dezelfde controle als in `legacy_scripts/link.py` en `build.py`, met actielijst.
3. **Mappingtabel genereren** voor het PICS-tool (formaat van het tabblad Vlees), zodat die niet handmatig bijgehouden wordt.
4. **PICS-import genereren** uit een Z-afslag (plus per portie, min op bulk), met controles en waarschuwingen.
5. **Voorraad en inkoop**: inkomende goederen en TO's vastleggen, voorraad per bulk.
6. **RE-import genereren** voor nieuwe items en bijwerken.

Randvoorwaarden: gedeelde schijf, gebruik door meerdere collega's tegelijk, geen installatie voor collega's (liefst Excel of een eenvoudige webpagina), eenvoudig foutherstel. Keuze van techniek (Python + SQLite met eenvoudige webinterface, of Excel-macro) is nog open: bespreek dit eerst met de gebruiker.

## 9. Eerste stappen in Claude Code

1. Lees `CLAUDE.md` en dit document.
2. Zet de bronbestanden in `data/` en draai `legacy_scripts/load.py` + `link.py` (pas paden aan) om de koppelstatus opnieuw te bepalen.
3. Vraag de gebruiker om een verse RE-export en een vlees-Z-afslag.
4. Stel samen met de gebruiker vast welke techniek en welke eerste functie (aanbeveling: koppelcontrole + mappingtabel + PICS-import voor vlees).
