"""Volledige Z-afslag (hele weegschaal) indelen, controleren en omzetten naar een PICS-lijst.

Stap 1: lees_z_afslag + controleer_periode
Stap 2: deel_in -> tabel met per regel een categorie, voorstel en melding (aanpasbaar)
Stap 3: pics_regels -> CSV-regels uit de (aangepaste) tabel, met validatie
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from .bronnen import Mapping, MappingRegel, getal, tekst
from .instellingen import Regels
from .koppeling import Koppelresultaat, plu_naar_artnr
from .pics import formatteer

VLEES = "Vlees"
VLEES_GEEN_BULK = "Vlees, geen bulk"
KAAS = "Kaas"
KAAS_GEEN_BULK = "Kaas, geen bulk"
BUITEN = "Buiten scope"
ONBEKEND = "Onbekend"

KOLOMMEN = ["Meenemen", "PLU", "Omschrijving", "Leverancier", "Subgroep", "Categorie", "Eenheid",
            "Hoeveelheid", "Portie ART NR", "Bulk SKU", "Bulk afboeken", "Melding"]


# ---------------------------------------------------------------- stap 1

@dataclass
class Periode:
    van: date | None
    tm: date | None
    meldingen: list[str] = field(default_factory=list)

    @property
    def tekst(self) -> str:
        if not self.van:
            return "onbekend"
        return f"{_dag(self.van)} {self.van:%d-%m-%Y} t/m {_dag(self.tm)} {self.tm:%d-%m-%Y}"


def controleer_periode(bestandsnaam: str, vandaag: date | None = None) -> Periode:
    """Periode uit 'Artikelen_van_YYYYMMDD_tm_YYYYMMDD'. Verwacht: maandag t/m zondag, 7 dagen."""
    m = re.search(r"van_(\d{8})_tm_(\d{8})", bestandsnaam)
    if not m:
        return Periode(None, None, ["Periode niet te herkennen uit de bestandsnaam (verwacht Artikelen_van_JJJJMMDD_tm_JJJJMMDD)."])
    try:
        van = date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:]))
        tm = date(int(m[2][:4]), int(m[2][4:6]), int(m[2][6:]))
    except ValueError:
        return Periode(None, None, ["Datum in de bestandsnaam is ongeldig."])
    p = Periode(van, tm)
    if van.weekday() != 0:
        p.meldingen.append(f"Begint niet op maandag maar op {_dag(van)}.")
    if tm.weekday() != 6:
        p.meldingen.append(f"Eindigt niet op zondag maar op {_dag(tm)}.")
    if (tm - van).days != 6:
        p.meldingen.append(f"Periode is {(tm - van).days + 1} dagen in plaats van 7.")
    vandaag = vandaag or date.today()
    if tm >= vandaag:
        p.meldingen.append("De periode is nog niet voorbij.")
    elif vandaag - tm > timedelta(days=14):
        p.meldingen.append(f"Dit is niet de afgelopen week (eindigde {(vandaag - tm).days} dagen geleden). Is er een week overgeslagen of al verwerkt?")
    return p


def _dag(d: date) -> str:
    return ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"][d.weekday()]


# ---------------------------------------------------------------- mapping

def mapping_uit_koppeling(k: Koppelresultaat) -> Mapping:
    m = Mapping(tabbladen=["koppelcontrole"])
    for r in k.plus.itertuples(index=False):
        m.regels[int(r.PLU)] = MappingRegel(int(r.PLU), r.artnr, r.bulk_sku, "koppelcontrole", 0)
    return m


# ---------------------------------------------------------------- stap 2

@dataclass
class Indeling:
    tabel: pd.DataFrame
    totaal_kg: Decimal | None = None
    totaal_st: Decimal | None = None
    overgeslagen: list[str] = field(default_factory=list)


def deel_in(z: pd.DataFrame, vlees: Mapping, kaas: Mapping | None, regels: Regels,
            re_df: pd.DataFrame | None = None, bulk_namen: dict[str, str] | None = None) -> Indeling:
    cfg = regels.afslag_indeling
    kaas_van, kaas_tot = cfg.get("kaas_plu_bereik", [1000, 1999])
    kaas_sub = set(cfg.get("kaas_subgroepen", ["Kaas"]))
    kaas_mee = bool(cfg.get("kaas_meenemen", False))
    buiten_sub = set(cfg.get("buiten_scope_subgroepen", []))
    buiten_lev = set(cfg.get("buiten_scope_leveranciers", []))
    re_skus = set(re_df.index) if re_df is not None else None
    bulk_namen = bulk_namen or {}
    per_stuk = {int(k): w for k, w in cfg.get("per_stuk", {}).items()}

    res = Indeling(tabel=pd.DataFrame(columns=KOLOMMEN))
    rijen = []
    for nr, rij in enumerate(z.to_dict("records"), start=2):
        winkel = tekst(rij.get("Winkel"))
        if winkel == "Totaal":
            res.totaal_kg = getal(rij.get("Gewicht"))
            res.totaal_st = getal(rij.get("Aantallen"))
            continue
        if winkel == "":
            continue
        art = getal(rij.get("Artikel"))
        if art is None or art == 0:
            continue  # o.a. 'In % excl derving'
        plu = int(art.to_integral_value(rounding=ROUND_HALF_UP))
        omschr = tekst(rij.get("Omschrijving1"))
        lev = tekst(rij.get("Leverancier"))
        sub = tekst(rij.get("Subgroep omschrijving"))

        aantal, gewicht = getal(rij.get("Aantallen")), getal(rij.get("Gewicht"))
        if aantal is not None and aantal != 0:
            eenheid, hoeveelheid = "st", aantal
        elif gewicht is not None and gewicht != 0:
            eenheid, hoeveelheid = "kg", gewicht
        else:
            res.overgeslagen.append(f"Rij {nr}: PLU {plu} {omschr} heeft geen aantal en geen gewicht.")
            continue

        meld: list[str] = []
        artnr, bulk, mee = "", "", False
        if plu in regels.negeren:
            cat = BUITEN
            meld.append(f"Buiten scope (genegeerd: {regels.negeren[plu]})")
        elif plu in vlees.regels:
            m = vlees.regels[plu]
            artnr, bulk = m.artnr, m.bulk_sku
            cat, mee = (VLEES, True) if bulk else (VLEES_GEEN_BULK, True)
            if not bulk:
                meld.append(regels.open_redenen.get(plu, "Geen bulk in RE") + ": portie wordt bijgeboekt, geen bulk afgeboekt")
            if plu in regels.samengesteld:
                meld.append("Samengesteld artikel: afboeking van maar een bulk, controleer")
        elif (kaas and plu in kaas.regels) or kaas_van <= plu <= kaas_tot or sub in kaas_sub or lev in regels.kaas_leveranciers:
            if kaas and plu in kaas.regels:
                artnr, bulk = kaas.regels[plu].artnr, kaas.regels[plu].bulk_sku
                cat, mee = (KAAS if bulk else KAAS_GEEN_BULK), kaas_mee
                if not bulk:
                    meld.append("Geen kaas-bulk: portie wordt bijgeboekt, geen bulk afgeboekt")
            else:
                cat, artnr = KAAS_GEEN_BULK, plu_naar_artnr(plu)
                if re_skus is not None and artnr not in re_skus:
                    meld.append("Kaas-PLU staat niet in RE, maar wordt wel verkocht: RE of weegschaal bijwerken")
                    artnr = ""
                else:
                    meld.append("Kaas-PLU niet in de kaas-mapping: vul bulk in of laat weg")
            if not kaas_mee:
                meld.insert(0, "Kaas gaat via het PICS-tool (Nick)")
        elif sub in buiten_sub or lev in buiten_lev:
            cat = BUITEN
            meld.append(f"Buiten scope ({sub or lev})")
        else:
            cat = ONBEKEND
            artnr = plu_naar_artnr(plu)
            if re_skus is not None and artnr not in re_skus:
                meld.append(f"PLU staat niet (meer) in RE, maar wordt nog verkocht: weegschaal of RE bijwerken")
                artnr = ""
            else:
                meld.append("PLU niet in de mapping (geen vleesklasse in RE?): vul bulk in of laat weg")

        afboeken = hoeveelheid
        if eenheid == "st" and cat in (VLEES, VLEES_GEEN_BULK, KAAS, KAAS_GEEN_BULK):
            regel_st = per_stuk.get(plu)
            if regel_st is None:
                meld.append("Per stuk verkocht, geen gewicht per stuk bekend: controleer 'Bulk afboeken' "
                            "(staat nu gelijk aan het aantal) en leg het vast in config")
            elif regel_st != "stuk":
                afboeken = hoeveelheid * Decimal(str(regel_st))
        if hoeveelheid < 0:
            meld.append("Negatieve hoeveelheid (retour?)")
        if re_skus is not None and mee:
            for s in (artnr, bulk):
                if s and s not in re_skus:
                    meld.append(f"SKU {s} niet in RE-export")

        rijen.append({
            "Meenemen": mee, "PLU": plu, "Omschrijving": omschr, "Leverancier": lev, "Subgroep": sub,
            "Categorie": cat, "Eenheid": eenheid, "Hoeveelheid": float(hoeveelheid),
            "Portie ART NR": artnr, "Bulk SKU": _bulk_label(bulk, bulk_namen),
            "Bulk afboeken": float(afboeken) if bulk else None, "Melding": "; ".join(meld),
        })
    if rijen:
        t = pd.DataFrame(rijen, columns=KOLOMMEN)
        for plu, groep in t.groupby("PLU"):
            if groep.Omschrijving.nunique() > 1:
                namen = " / ".join(groep.Omschrijving.unique())
                for i in groep.index:
                    t.at[i, "Melding"] = "; ".join(x for x in [t.at[i, "Melding"],
                        f"PLU {plu} staat meerdere keren in de afslag met een andere omschrijving ({namen}): weegschaal controleren"] if x)
        res.tabel = t
    return res


def _bulk_label(sku: str, namen: dict[str, str]) -> str:
    if not sku:
        return ""
    return f"{sku} | {namen[sku]}" if sku in namen else sku


def bulk_sku(label) -> str:
    """'2024700092606 | Bulk 2098, Buik' -> '2024700092606'."""
    s = tekst(label)
    return s.split("|", 1)[0].strip()


def totaalcontrole(ind: Indeling, tolerantie: float = 0.01) -> list[tuple[str, bool, str]]:
    """Som van alle regels (ongeacht categorie) tegen de totaalregel, apart voor kg en stuks."""
    t = ind.tabel
    uit = []
    for eenheid, totaal, naam in (("kg", ind.totaal_kg, "Gewicht (kg)"), ("st", ind.totaal_st, "Aantallen (st)")):
        som = Decimal(str(round(t.loc[t.Eenheid == eenheid, "Hoeveelheid"].sum(), 6))) if len(t) else Decimal(0)
        if totaal is None:
            uit.append((naam, som == 0, f"som regels {formatteer(som)}, geen totaalregel"))
            continue
        ok = abs(som - totaal) <= Decimal(str(tolerantie))
        uit.append((naam, ok, f"som regels {formatteer(som)}, totaalregel {formatteer(totaal)}"))
    return uit


# ---------------------------------------------------------------- stap 3

@dataclass
class PicsLijst:
    regels: list[str]
    porties: dict[str, Decimal]
    bulks: dict[str, Decimal]
    fouten: list[str]
    waarschuwingen: list[str]


def _dec(v) -> Decimal | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return Decimal(str(round(float(v), 6)))


def pics_regels(tabel: pd.DataFrame, re_skus: set[str] | None = None) -> PicsLijst:
    """Maak de PICS-regels uit de (aangepaste) tabel. Alleen rijen met Meenemen = waar.

    Portie: + Hoeveelheid op Portie ART NR. Bulk: - 'Bulk afboeken' op Bulk SKU.
    Eerst alle porties, dan alle bulks (zoals de macro), in volgorde van de afslag.
    """
    porties: dict[str, Decimal] = {}
    bulks: dict[str, Decimal] = {}
    fouten, waarsch = [], []
    for r in tabel[tabel.Meenemen.fillna(False).astype(bool)].to_dict("records"):
        plu = r["PLU"]
        art = tekst(r["Portie ART NR"])
        if art.endswith(".0"):
            art = art[:-2]
        q = _dec(r["Hoeveelheid"])
        if not art.isdigit():
            fouten.append(f"PLU {plu}: Portie ART NR ontbreekt of is geen nummer.")
            continue
        if q is None or q == 0:
            fouten.append(f"PLU {plu}: hoeveelheid is leeg of 0.")
            continue
        if re_skus is not None and art not in re_skus:
            fouten.append(f"PLU {plu}: Portie ART NR {art} bestaat niet in de RE-export.")
            continue
        b = bulk_sku(r["Bulk SKU"])
        af = _dec(r["Bulk afboeken"])
        if b:
            if not b.isdigit():
                fouten.append(f"PLU {plu}: Bulk SKU '{b}' is geen nummer.")
                continue
            if re_skus is not None and b not in re_skus:
                fouten.append(f"PLU {plu}: Bulk SKU {b} bestaat niet in de RE-export.")
                continue
            if af is None:
                fouten.append(f"PLU {plu}: 'Bulk afboeken' is leeg terwijl er een bulk is ingevuld.")
                continue
            if r.get("Eenheid") == "st" and af == q and "geen gewicht per stuk" in tekst(r.get("Melding")):
                waarsch.append(f"PLU {plu}: per stuk ({formatteer(q)} st) en bulk afboeken is ook {formatteer(af)}: klopt dat in kg?")
        elif af not in (None, Decimal(0)):
            waarsch.append(f"PLU {plu}: 'Bulk afboeken' ingevuld maar geen Bulk SKU: genegeerd.")
        porties[art] = porties.get(art, Decimal(0)) + q
        if b:
            bulks[b] = bulks.get(b, Decimal(0)) - af
    regels = [f"{k},{formatteer(v)}" for k, v in porties.items()] + [f"{k},{formatteer(v)}" for k, v in bulks.items()]
    return PicsLijst(regels, porties, bulks, fouten, waarsch)


# ---------------------------------------------------------------- overzicht per bulk

GEEN_BULK = "(geen bulk)"
OVERZICHT_KOLOMMEN = ["Bulk", "Regel", "SKU", "PLU", "Omschrijving", "Mutatie", "Eenheid", "Van bulk", "Bulk-eenheid", "Controle"]


@dataclass
class BulkOverzicht:
    tabel: pd.DataFrame          # een blok per bulk: bulkregel (-), portieregels (+), totaalregel
    porties_kg: Decimal
    porties_st: Decimal
    bulks_kg: Decimal
    bulks_st: Decimal
    zonder_bulk_kg: Decimal
    zonder_bulk_st: Decimal
    verschillen: int


def bulk_eenheid(eenheid: str, plu: int, regels: Regels) -> str:
    """Eenheid waarin de bulk wordt afgeboekt: kg, behalve stuksartikelen waarvan de bulk per stuk telt."""
    if eenheid != "st":
        return "kg"
    w = regels.afslag_indeling.get("per_stuk", {}).get(str(plu))
    return "kg" if w not in (None, "stuk") else "st"


def overzicht_per_bulk(tabel: pd.DataFrame, regels: Regels, namen: dict[str, str] | None = None) -> BulkOverzicht:
    """Per bulk: wat eraf gaat, op welke portie-artikelen het erbij komt, en of dat sluit.

    Alleen regels met Meenemen = waar. 'Van bulk' is de verkochte portie omgerekend naar de eenheid van
    de bulk (stuks x kg per stuk). De som daarvan moet gelijk zijn aan wat er van de bulk afgaat; wijkt
    'Bulk afboeken' af (met de hand aangepast), dan staat er een verschil bij het totaal.
    """
    namen = namen or {}
    t = tabel[tabel.Meenemen.fillna(False).astype(bool)].copy()
    t["_bulk"] = t["Bulk SKU"].map(bulk_sku)
    nul = Decimal(0)
    som = {"pk": nul, "ps": nul, "bk": nul, "bs": nul, "zk": nul, "zs": nul}
    rijen, verschillen = [], 0
    volgorde = sorted(t._bulk.unique(), key=lambda s: (s == "", namen.get(s, s).lower()))
    for b in volgorde:
        g = t[t._bulk == b]
        label = f"{b} | {namen[b]}" if b in namen else (b or GEEN_BULK)
        porties, af, eenh_bulk = [], nul, set()
        for r in g.to_dict("records"):
            q = _dec(r["Hoeveelheid"]) or nul
            be = bulk_eenheid(r["Eenheid"], int(r["PLU"]), regels)
            # 'van bulk' = verkocht, omgerekend naar de bulk-eenheid; 'af' = wat er echt wordt afgeboekt (kan aangepast zijn)
            factor = regels.afslag_indeling.get("per_stuk", {}).get(str(r["PLU"]))
            van = q * Decimal(str(factor)) if (r["Eenheid"] == "st" and be == "kg") else q
            eenh_bulk.add(be)
            som["ps" if r["Eenheid"] == "st" else "pk"] += q
            if not b:
                som["zs" if r["Eenheid"] == "st" else "zk"] += q
            af += (_dec(r["Bulk afboeken"]) or nul) if b else nul
            porties.append({"Bulk": label, "Regel": "+ portie", "SKU": tekst(r["Portie ART NR"]).removesuffix(".0"),
                            "PLU": int(r["PLU"]), "Omschrijving": r["Omschrijving"], "Mutatie": float(q),
                            "Eenheid": r["Eenheid"], "Van bulk": float(van) if b else None,
                            "Bulk-eenheid": be if b else "", "Controle": ""})
        be = "/".join(sorted(eenh_bulk))
        if b:
            som["bs" if be == "st" else "bk"] += af
            rijen.append({"Bulk": label, "Regel": "- bulk", "SKU": b, "PLU": None,
                          "Omschrijving": namen.get(b, ""), "Mutatie": -float(af), "Eenheid": be,
                          "Van bulk": None, "Bulk-eenheid": "", "Controle": ""})
        rijen.extend(porties)
        if b:
            totaal_van = sum((_dec(p["Van bulk"]) or nul for p in porties), nul)
            ok = abs(totaal_van - af) < Decimal("0.0005") and len(eenh_bulk) == 1
            verschillen += not ok
            controle = "OK" if ok else ("Gemengde eenheden" if len(eenh_bulk) > 1 else
                                         f"Verschil {formatteer(totaal_van - af)}")
            rijen.append({"Bulk": label, "Regel": "= totaal", "SKU": "", "PLU": None,
                          "Omschrijving": f"{len(porties)} portie(s): erbij {formatteer(totaal_van)} {be}, "
                                          f"eraf {formatteer(af)} {be}",
                          "Mutatie": float(totaal_van - af), "Eenheid": be, "Van bulk": float(totaal_van),
                          "Bulk-eenheid": be, "Controle": controle})
        else:
            rijen.append({"Bulk": label, "Regel": "= totaal", "SKU": "", "PLU": None,
                          "Omschrijving": f"{len(porties)} portie(s) zonder bulk: alleen bijgeboekt", "Mutatie": None,
                          "Eenheid": "", "Van bulk": None, "Bulk-eenheid": "", "Controle": "Let op: geen afboeking"})
    return BulkOverzicht(pd.DataFrame(rijen, columns=OVERZICHT_KOLOMMEN), som["pk"], som["ps"], som["bk"], som["bs"],
                         som["zk"], som["zs"], verschillen)
