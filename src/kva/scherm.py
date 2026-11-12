"""Scherm (Streamlit) met stappenplan voor de wekelijkse voorraadcorrectie.

Starten: dubbelklik start_scherm.cmd, of: python -m streamlit run src/kva/scherm.py
"""

from __future__ import annotations

import io
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from kva.bronnen import Mapping, lees_mappingtabel, lees_re_export, lees_weegschaal, lees_z_afslag  # noqa: E402
from kva.instellingen import BronFout, laad_instellingen, laad_regels, uitvoermap, zoek_bestand  # noqa: E402
from kva.koppeling import koppel  # noqa: E402
from kva.opslag import lees_log, schrijf_log, sha256, vrije_naam  # noqa: E402
from kva.pics import formatteer  # noqa: E402
from kva.verwerking import (  # noqa: E402
    BUITEN, KAAS, KAAS_GEEN_BULK, ONBEKEND, VLEES, VLEES_GEEN_BULK, controleer_periode, deel_in,
    mapping_uit_koppeling, overzicht_per_bulk, pics_regels, totaalcontrole,
)
from kva.maand import archiveer, controleer_dekking, lees_re_verkoop, periode_uit_naam, vergelijk  # noqa: E402
from kva.voorraad import BULK, STUK, lees_tellijst, maak_tellijst, telverschillen, voorraad_lijst  # noqa: E402
from kva import stuksbalans as sb  # noqa: E402

st.set_page_config(page_title="Voorraadcorrectie kaas & vlees", page_icon="🥩", layout="wide")

LOGO = Path(__file__).resolve().parents[2] / "assets" / "bondigro_logo.png"
STAPPEN = ["Z-afslag kiezen", "Controleren", "PICS-lijst maken", "Importeren in RetailEdge"]
DAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MAANDEN = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
.kva-stappen {display: flex; gap: .5rem; margin: .25rem 0 1.25rem 0; flex-wrap: wrap;}
.kva-stap {flex: 1 1 160px; padding: .55rem .8rem; border-radius: .5rem; background: #EAF3FA;
           color: #5B6B7C; font-size: .9rem; border: 1px solid #D2E0EC;}
.kva-stap b {display: block; font-size: .75rem; letter-spacing: .04em; text-transform: uppercase;}
.kva-stap.nu {background: #1B6FB5; color: #fff; border-color: #1B6FB5;}
.kva-stap.klaar {background: #E1EEF9; color: #1D2B3A;}
.kva-kaart {border: 1px solid #D2E0EC; border-radius: .6rem; padding: .9rem 1rem; height: 100%;}
.kva-kaart .label {color: #5B6B7C; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em;}
.kva-kaart .waarde {font-size: 1.3rem; font-weight: 700; color: #1D2B3A; margin: .15rem 0;}
.kva-kaart .uitleg {color: #5B6B7C; font-size: .85rem;}
.kva-ok {color: #1E7B45;} .kva-let {color: #C2571A;}
.kva-welkom {font-size: 1.05rem; color: #1D2B3A; margin: -.25rem 0 1rem 0;}
.kva-todo {border-left: 4px solid #1B6FB5; background: #F5F9FD; padding: .6rem 1rem; border-radius: .4rem; margin-bottom: .4rem;}
.kva-todo.klaar {border-left-color: #1E7B45; color: #5B6B7C;}
.kva-todo.let {border-left-color: #C2571A; background: #FDF5EE;}
.kva-bron {font-size: .82rem; line-height: 1.35; margin: 0 0 .3rem 0;}
.kva-bron span {color: #5B6B7C;}
</style>
""", unsafe_allow_html=True)

BEWERKBAAR = ["Meenemen", "Hoeveelheid", "Portie ART NR", "Bulk SKU", "Bulk afboeken"]
VOLGORDE = ["Meenemen", "PLU", "Omschrijving", "Melding", "Categorie", "Eenheid", "Hoeveelheid",
            "Bulk afboeken", "Bulk SKU", "Portie ART NR", "Leverancier", "Subgroep"]
ROUTINE = ("Kaas gaat via het PICS-tool", "Buiten scope (")


def actie_nodig(melding: str) -> bool:
    """Melding met iets anders dan routine (kaas via PICS-tool, buiten scope)."""
    return any(d and not d.startswith(ROUTINE) for d in melding.split("; "))


# ---------------------------------------------------------------- bronnen

@st.cache_resource(show_spinner="Bronbestanden inlezen...")
def laad_bronnen(re_pad: str, re_tijd: float, weeg_pad: str, weeg_tijd: float, tool_pad: str, tool_tijd: float):
    regels = laad_regels()
    re_df = lees_re_export(Path(re_pad), regels)
    weeg = lees_weegschaal(Path(weeg_pad))
    k_vlees, k_kaas = koppel(weeg, re_df, regels, "vlees"), koppel(weeg, re_df, regels, "kaas")
    # kaas: koppeling uit RE; PLU's die daar ontbreken maar wel in het Kaas-tabblad van het PICS-tool staan, als aanvulling
    tool = lees_mappingtabel(Path(tool_pad), regels.pics_menu_tabblad)
    kaas = Mapping(regels={p: m for p, m in tool.regels.items() if m.tabblad == "Kaas"})
    kaas.regels.update(mapping_uit_koppeling(k_kaas).regels)
    namen = dict(zip(k_vlees.bulks.Inv_Sku, k_vlees.bulks.Inv_Desc)) | dict(zip(k_kaas.bulks.Inv_Sku, k_kaas.bulks.Inv_Desc))
    return regels, re_df, (k_vlees, k_kaas), kaas, namen


def dagen_oud(p: Path) -> int:
    return (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).days


def bronnen_zijbalk(inst):
    if LOGO.exists():
        st.logo(str(LOGO), size="large")
    paden, regels_html, oud = {}, [], False
    try:
        for sleutel, naam in (("re_export", "RE-export"), ("weegschaal", "Weegschaal"), ("pics_tool", "PICS-tool")):
            p = zoek_bestand(inst["bronnen"][sleutel])
            paden[sleutel] = p
            d = dagen_oud(p)
            te_oud = sleutel == "re_export" and d > 7
            oud |= te_oud
            leeftijd = "vandaag" if d == 0 else "gisteren" if d == 1 else f"{d} dagen"
            regels_html.append(f'<div class="kva-bron" title="{p.name}">{"🟠" if te_oud else "🟢"} '
                               f'<b>{naam}</b> <span>· {leeftijd}</span></div>')
    except BronFout as e:
        st.sidebar.error(str(e))
        st.stop()
    with st.sidebar.expander("Bronbestanden" + (" ⚠️" if oud else " ✓"), expanded=oud):
        st.markdown("".join(regels_html), unsafe_allow_html=True)
        if oud:
            st.caption("De RE-export is ouder dan een week: zet een verse export in de map RE-export.")
        st.caption("Steeds het nieuwste bestand uit de mappen op de gedeelde schijf. Muis op een naam = bestandsnaam.")
        if st.button("↻ Opnieuw inlezen", use_container_width=True):
            laad_bronnen.clear()
            st.rerun()
    bron = laad_bronnen(*(x for k in ("re_export", "weegschaal", "pics_tool")
                          for x in (str(paden[k]), paden[k].stat().st_mtime)))
    return bron, paden


def kop(nummer: int, titel: str, klaar: bool):
    st.markdown(f"#### {'✅ ' if klaar else ''}Stap {nummer} · {titel}")


def koptekst():
    st.markdown("## Voorraadcorrectie kaas & vlees")
    st.caption("Elke week: de Z-afslag van de weegschaal omzetten naar een PICS-lijst voor RetailEdge. "
                   "Wat er van de bulk is gesneden, gaat eraf; wat er als portie is verkocht, komt erbij.")


def stappenbalk(huidig: int):
    blokken = []
    for i, naam in enumerate(STAPPEN, start=1):
        klasse = "nu" if i == huidig else "klaar" if i < huidig else ""
        teken = "✓ " if i < huidig else ""
        blokken.append(f'<div class="kva-stap {klasse}"><b>Stap {i}</b>{teken}{naam}</div>')
    st.markdown(f'<div class="kva-stappen">{"".join(blokken)}</div>', unsafe_allow_html=True)


def kaart(kolom, label: str, waarde: str, uitleg: str, ok: bool = True):
    kolom.markdown(
        f'<div class="kva-kaart"><div class="label">{label}</div>'
        f'<div class="waarde {"kva-ok" if ok else "kva-let"}">{waarde}</div>'
        f'<div class="uitleg">{uitleg}</div></div>', unsafe_allow_html=True)


def datum_kort(d: date) -> str:
    return f"{DAGEN[d.weekday()]} {d.day} {MAANDEN[d.month - 1]}"


def vorige_week(vandaag: date | None = None) -> tuple[date, date]:
    """Maandag en zondag van de laatste volledige week."""
    vandaag = vandaag or date.today()
    maandag = vandaag - timedelta(days=vandaag.weekday() + 7)
    return maandag, maandag + timedelta(days=6)


def stuksbalans_nu() -> sb.Balans:
    """Stand van de porties volgens de huidige RE-export; bewaart hem in de historie (een keer per export)."""
    regels, re_df, koppelingen, _, _ = CTX["bron"]
    p, inst = CTX["paden"]["re_export"], CTX["inst"]
    tijd = datetime.fromtimestamp(p.stat().st_mtime)
    stand = sb.stuks_stand(voorraad_lijst(re_df, list(koppelingen), regels), re_df)
    map_ = CTX["uit"] / "stuksbalans"
    try:
        sb.bewaar_stand(map_, p.name, tijd, stand)
    except OSError:
        pass
    cfg = inst.get("stuksbalans", {})
    drempel = {"kg": float(cfg.get("drempel_kg", 0.5)), "st": float(cfg.get("drempel_st", 2))}
    return sb.beoordeel(stand, sb.lees_standen(map_), tijd, drempel)


def todo(tekst: str, soort: str = ""):
    st.markdown(f'<div class="kva-todo {soort}">{tekst}</div>', unsafe_allow_html=True)


def voorblad(koppelingen, paden, uit: Path):
    """Startscherm: wat moet er gebeuren, staat alles klaar, en hoe staan de porties ervoor."""
    van, tm = vorige_week()
    verwacht = f"Artikelen_van_{van:%Y%m%d}_tm_{tm:%Y%m%d}"
    log = sorted(lees_log(uit).values(), key=lambda r: r["datum"], reverse=True)
    al_gedaan = next((r for r in log if r["bestand"].startswith(verwacht)), None)
    re_oud = dagen_oud(paden["re_export"])
    balans = stuksbalans_nu()
    gemeten = balans.gemeten
    afwijk = gemeten[gemeten.Status != sb.OK]
    nonstock = balans.aantal(sb.NONSTOCK)
    slechter = int((balans.tabel.Trend == sb.SLECHTER).sum())

    st.markdown(f'<div class="kva-welkom">Te verwerken: week <b>{datum_kort(van)} t/m {datum_kort(tm)}</b> · '
                f'vandaag is het {datum_kort(date.today())}</div>', unsafe_allow_html=True)

    if re_oud > 7:
        todo(f"⚠️ <b>Zet een verse RE-export in de map RE-export.</b> De huidige is {re_oud} dagen oud.", "let")
    if al_gedaan:
        todo(f"✅ De Z-afslag van deze week is verwerkt op {al_gedaan['datum']}.", "klaar")
    else:
        todo(f"👉 <b>Verwerk de Z-afslag van deze week.</b> Kies hieronder <code>{verwacht}.XLS</code>.")
    open_k = [k for k in koppelingen if k.open]
    if open_k:
        todo("⚠️ " + " · ".join(f"{k.soort.capitalize()}: {k.open} PLU's zonder bulk" for k in open_k)
             + ". Die worden niet van een bulk afgeboekt.", "let")
    if nonstock:
        todo(f"⚠️ <b>{nonstock} porties staan in RE op NonStock.</b> Zet ze op Stock, anders houdt RE geen voorraad bij.", "let")
    if not afwijk.empty:
        todo(f"⚠️ <b>{len(afwijk)} porties staan niet rond 0</b> ({balans.aantal(sb.MIN)} in de min, "
             f"{balans.aantal(sb.PLUS)} in de plus). Zie <i>Stuksbalans</i> hieronder.", "let")
    elif not gemeten.empty:
        todo("✅ Alle porties staan rond 0.", "klaar")

    c1, c2, c3, c4 = st.columns(4)
    for kol, k in zip((c1, c2), koppelingen):
        kaart(kol, f"{k.soort.capitalize()}: koppeling", f"{k.gekoppeld} van {k.aantal}",
              "Alle PLU's hebben een bulk." if k.open == 0 else f"{k.open} PLU's zonder bulk.", k.open == 0)
    kaart(c3, "Porties rond 0", f"{len(gemeten) - len(afwijk)} van {len(gemeten)}",
          f"{balans.aantal(sb.MIN)} min · {balans.aantal(sb.PLUS)} plus"
          + (f" · {nonstock} NonStock niet meegeteld" if nonstock else ""), afwijk.empty)
    if balans.vorige:
        kaart(c4, "Sinds vorige meting", f"{balans.rechtgetrokken} rechtgetrokken",
              f"{slechter} slechter · vorige stand {balans.vorige:%d-%m %H:%M}", slechter == 0)
    else:
        kaart(c4, "Sinds vorige meting", "Eerste meting", "Bij de volgende RE-export zie je wat is rechtgetrokken.")
    st.write("")
    return log, balans


def toon_stuksbalans(balans: sb.Balans, kort: bool):
    """De porties die niet rond 0 staan, met de trend tegen de vorige meting."""
    t = balans.tabel
    if not CTX["inst"].get("stuksbalans", {}).get("nulmeting"):
        st.warning("**Nog geen nulmeting van de porties.** De stand in RE komt nog uit de tijd dat de porties niet "
                   "werden gecorrigeerd (veel NonStock en grote minnen). Tel de porties, zet ze in RE op de telling "
                   "en geef de datum door; die komt in `config/instellingen.toml` bij `nulmeting`. Tot dan zegt vooral "
                   "de kolom **Verandering** (sinds de vorige meting) iets.")
    with st.popover("Wat betekent dit?"):
        st.markdown("""
Na een Z-afslag-correctie hoort een portie **rond 0** te staan: de productie van de week komt erbij (PICS-lijst),
de verkoop gaat eraf (kassa).

- **Plus**: meer geproduceerd dan verkocht. Ligt nog in de toonbank, is weggegooid, of verkocht onder een ander nummer.
- **Min**: meer verkocht dan geproduceerd. Handmatig gewogen aan de kassa, verkeerde PLU, of de afslag mist iets.
- **Trend**: vergeleken met de vorige RE-export. *Rechtgetrokken* = de week erna weer rond 0.

Maak de RE-export het liefst direct na het importeren van de PICS-lijst, voordat de winkel opengaat.
Anders zit de verkoop van de nieuwe week er al in, maar de productie nog niet.
""")
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    keuze = c1.multiselect("Toon", [sb.MIN, sb.PLUS, sb.NONSTOCK, sb.OK], [sb.MIN, sb.PLUS], key=f"sb_keuze_{kort}")
    soort = c2.multiselect("Soort", ["Vlees", "Kaas"], ["Vlees", "Kaas"], key=f"sb_soort_{kort}")
    zicht = t[t.Status.isin(keuze) & t.Soort.isin(soort)]
    kolommen = ["Soort", "PLU", "Omschrijving", "Eenheid", "Voorraad", "Vorige stand", "Verandering", "Trend",
                "Status", "Waarde", "SKU", "Stocktype"]
    st.dataframe(zicht[kolommen].head(15) if kort else zicht[kolommen], hide_index=True, use_container_width=True,
                 height="auto" if kort else 520,
                 column_config={"PLU": st.column_config.NumberColumn(format="%d"),
                                "Voorraad": st.column_config.NumberColumn(format="%.3f"),
                                "Vorige stand": st.column_config.NumberColumn(format="%.3f"),
                                "Verandering": st.column_config.NumberColumn(format="%+.3f"),
                                "Waarde": st.column_config.NumberColumn("Waarde $", format="%.2f")})
    st.caption(f"Stand volgens de RE-export van {balans.stand:%d-%m-%Y %H:%M}."
               + (f" De 15 grootste van {len(zicht)}; alles staat bij *Voorraad & tellijsten* › Stuksbalans."
                  if kort and len(zicht) > 15 else ""))
    st.download_button("Download stuksbalans (Excel)", excel_bytes({"Stuksbalans": t}),
                       file_name=f"Stuksbalans_{balans.stand:%Y_%m_%d}.xlsx", key=f"sb_dl_{kort}")


def laatst_verwerkt(log: list[dict]):
    with st.expander(f"Eerder verwerkt ({len(log)})", expanded=False):
        if not log:
            st.caption("Nog niets verwerkt.")
            return
        st.dataframe(pd.DataFrame([{"Verwerkt op": r["datum"], "Z-afslag": r["bestand"],
                                    "PICS-lijst": Path(r["uitvoer"]).name} for r in log[:10]]),
                     hide_index=True, use_container_width=True)


def uitleg():
    with st.expander("Hoe werkt het?"):
        st.markdown("""
1. **Z-afslag kiezen.** Exporteer op de weegschaal *Artikelen* van maandag t/m zondag en kies dat bestand hier.
   De hele weegschaal mag erin staan; fruit, bakkerij en testartikelen worden vanzelf overgeslagen.
2. **Controleren.** De app laat zien wat er per PLU gebeurt. Alleen regels met een melding vragen aandacht.
3. **PICS-lijst maken.** Eén klik; de lijst wordt opgeslagen in de map `uitvoer`.
4. **Importeren in RetailEdge.** Volg de stappen onderaan. Kies altijd **Append**, nooit Overwrite.
""")


# ---------------------------------------------------------------- pagina

def pagina_week():
    uit = CTX["uit"]
    (regels, re_df, (k, k_kaas), kaas, bulk_namen), paden = CTX["bron"], CTX["paden"]
    ss = st.session_state

    koptekst()
    huidig = 4 if "opgeslagen" in ss else 3 if "pics" in ss else 2 if ss.get("upload") is not None else 1
    stappenbalk(huidig)

    # ---------------- stap 1
    if ss.get("upload") is None:
        log, balans = voorblad((k, k_kaas), paden, uit)
    stap1 = st.container(border=True)
    with stap1:
        kop(1, "Kies de Z-afslag van afgelopen week (maandag t/m zondag)", ss.get("upload") is not None)
        bestand = st.file_uploader("Sleep het bestand hierheen of klik op *Browse files*. "
                                   "Het is de export van de hele weegschaal (.XLS, .xlsx of .csv).",
                                   type=["xls", "xlsx", "csv"], key="upload")
        if bestand is None:
            for s in ("tabel", "afslag", "pics", "opgeslagen"):
                ss.pop(s, None)
            st.caption("Te vinden op de gedeelde schijf, map *Slagerij en kaas administratie* › Z-afslagen.")
    if bestand is None:
        n = int((balans.gemeten.Status != sb.OK).sum())
        with st.expander(f"Stuksbalans: {n} porties niet rond 0" if n else "Stuksbalans: alles rond 0"):
            toon_stuksbalans(balans, kort=True)
        laatst_verwerkt(log)
        uitleg()
        st.stop()

    with stap1:
        data = bestand.getvalue()
        h = sha256(data)
        if ss.get("afslag", {}).get("hash") != h:
            for s in ("tabel", "pics", "opgeslagen"):
                ss.pop(s, None)
            archief = uit / "afslagen"
            archief.mkdir(exist_ok=True)
            pad = archief / bestand.name
            if not pad.exists() or sha256(pad.read_bytes()) != h:
                pad = vrije_naam(pad)
                pad.write_bytes(data)
            try:
                ind = deel_in(lees_z_afslag(pad), mapping_uit_koppeling(k), kaas, regels, re_df, bulk_namen)
            except BronFout as e:
                st.error(f"Dit bestand kan niet gelezen worden: {e}")
                st.stop()
            if ind.tabel.empty:
                st.error("Geen artikelregels gevonden in dit bestand.")
                st.stop()
            ss.afslag = {"hash": h, "naam": bestand.name, "pad": pad, "indeling": ind}
            ss.tabel = ind.tabel.copy()

        periode = controleer_periode(bestand.name)
        st.markdown(f"**Periode:** {periode.tekst}")
        for m in periode.meldingen:
            st.warning(m)
        log = lees_log(uit)
        eerder = log.get(h)
        if eerder is None and periode.van:
            # zelfde week, ander bestand (opnieuw geëxporteerd of al via het PICS-tool gedaan)
            sleutel = f"Artikelen_van_{periode.van:%Y%m%d}_tm_{periode.tm:%Y%m%d}"
            eerder = next((r for r in log.values() if r["bestand"].startswith(sleutel)), None)
        if eerder and "opgeslagen" not in ss:
            st.error(f"Deze afslag is al verwerkt op {eerder['datum']} ({Path(eerder['uitvoer']).name}). "
                     "Opnieuw importeren in RetailEdge boekt de voorraad dubbel.")
            if not st.checkbox("Ik weet het zeker: toch opnieuw verwerken"):
                st.stop()

    ind = ss.afslag["indeling"]
    tabel: pd.DataFrame = ss.tabel

    # ---------------- stap 2
    with st.container(border=True):
        kop(2, "Check bijzonderheden en pas eventueel aan", "pics" in ss)
        tel = tabel.Categorie.value_counts()
        cats = (VLEES, VLEES_GEEN_BULK, KAAS, KAAS_GEEN_BULK, BUITEN, ONBEKEND)
        kol = st.columns(len(cats))
        for c, cat in zip(kol, cats):
            c.metric(cat, int(tel.get(cat, 0)))

        for naam, ok, tekst_ in totaalcontrole(ind, regels.afslag_indeling.get("totaal_tolerantie", 0.01)):
            (st.success if ok else st.error)(f"Totaalcontrole {naam}: {tekst_} → {'OK' if ok else 'VERSCHIL, controleer de afslag'}")
        for m in ind.overgeslagen:
            st.info(m)

        st.markdown(
            "Hieronder per regel wat er gebeurt. **Meenemen** = komt in de PICS-lijst. "
            "Je kunt aanpassen: meenemen aan/uit, hoeveelheid, portie ART NR, bulk SKU en hoeveel er van de bulk "
            "afgaat. Kaas en vlees worden allebei verwerkt.")
        keuze = st.radio("Toon", ["Alleen actie nodig", "Alle meldingen", "Alle regels"], horizontal=True)
        if keuze == "Alleen actie nodig":
            zicht = tabel[tabel.Melding.map(actie_nodig)]
        elif keuze == "Alle meldingen":
            zicht = tabel[tabel.Melding.ne("")]
        else:
            zicht = tabel
        alleen = keuze
        opties = [""] + [f"{s} | {n}" for s, n in sorted(bulk_namen.items(), key=lambda x: x[1].lower())]
        bewerkt = st.data_editor(
            zicht, key=f"editor_{alleen}", hide_index=True, use_container_width=True, column_order=VOLGORDE,
            height=min(38 * (len(zicht) + 1) + 3, 700),
            disabled=[c for c in tabel.columns if c not in BEWERKBAAR],
            column_config={
                "Meenemen": st.column_config.CheckboxColumn(width="small"),
                "PLU": st.column_config.NumberColumn(format="%d", width="small"),
                "Hoeveelheid": st.column_config.NumberColumn(format="%.3f", width="small"),
                "Bulk afboeken": st.column_config.NumberColumn("Bulk afboeken (kg)", format="%.3f", width="small"),
                "Bulk SKU": st.column_config.SelectboxColumn(options=opties, width="large"),
                "Melding": st.column_config.TextColumn(width="large"),
                "Eenheid": st.column_config.TextColumn(width="small"),
            },
        )
        if not bewerkt[BEWERKBAAR].equals(zicht[BEWERKBAAR]):
            tabel.loc[bewerkt.index, BEWERKBAAR] = bewerkt[BEWERKBAAR]
            ss.pop("pics", None)
            ss.pop("opgeslagen", None)

    # ---------------- stap 3
    with st.container(border=True):
        kop(3, "PICS-lijst maken", "opgeslagen" in ss)
        if st.button("Controleer en maak de PICS-lijst", type="primary"):
            ss.pics = pics_regels(tabel, set(re_df.index))
            ss.pop("opgeslagen", None)
        lijst = ss.get("pics")
        if lijst is None:
            st.info("Klik op de knop als stap 2 klaar is.")
            st.stop()
        for f in lijst.fouten:
            st.error(f)
        for w in lijst.waarschuwingen:
            st.warning(w)
        if lijst.fouten:
            st.stop()
        ov = overzicht_per_bulk(tabel, regels, bulk_namen)
        c1, c2, c3 = st.columns(3)
        kaart(c1, "Erbij op porties", f"{formatteer(ov.porties_kg)} kg",
              f"en {formatteer(ov.porties_st)} stuks · {len(lijst.porties)} artikelen")
        kaart(c2, "Eraf van bulks", f"{formatteer(ov.bulks_kg)} kg",
              f"en {formatteer(ov.bulks_st)} stuks · {len(lijst.bulks)} bulks")
        zonder = ov.zonder_bulk_kg + ov.zonder_bulk_st
        goed = ov.verschillen == 0 and zonder == 0
        kaart(c3, "Controle", "Sluit ✓" if goed else "Let op",
              (f"{ov.verschillen} bulk(s) met verschil. " if ov.verschillen else "Per bulk: erbij = eraf. ")
              + (f"Zonder bulk: {formatteer(ov.zonder_bulk_kg)} kg en {formatteer(ov.zonder_bulk_st)} st alleen bijgeboekt."
                 if zonder else ""), goed)
        st.caption("Porties in stuks van een bulk in kg (zoals Rolladeschijf) tellen bij 'eraf' mee in kg: "
                   "aantal × gewicht per stuk.")
        with st.expander(f"Bekijk per bulk ({len(lijst.bulks)} bulks, {len(lijst.regels)} PICS-regels)"):
            toon_overzicht(ov.tabel)
            st.download_button("Download dit overzicht (Excel)", excel_bytes({"Per bulk": ov.tabel}),
                               file_name=f"{Path(ss.afslag['naam']).stem}_per_bulk.xlsx")

        if "opgeslagen" not in ss:
            if st.button("Opslaan"):
                stam = Path(ss.afslag["naam"]).stem
                csv_pad = vrije_naam(uit / f"{stam}_PICS_import.csv")
                with open(csv_pad, "w", encoding="ascii", newline="\r\n") as f:
                    f.write("\n".join(lijst.regels) + "\n")
                with pd.ExcelWriter(vrije_naam(uit / f"{stam}_verwerking.xlsx")) as xw:
                    tabel.to_excel(xw, sheet_name="Regels", index=False)
                    ov.tabel.to_excel(xw, sheet_name="Per bulk", index=False)
                schrijf_log(uit, ss.afslag["naam"], ss.afslag["hash"], csv_pad)
                ss.opgeslagen = csv_pad
                st.rerun()
            st.stop()
        csv_pad: Path = ss.opgeslagen
        st.success(f"Opgeslagen: {csv_pad}")
        st.download_button("Download PICS-lijst", csv_pad.read_bytes(), file_name=csv_pad.name, mime="text/csv")

    # ---------------- stap 4
    with st.container(border=True):
        kop(4, "Importeren in RetailEdge", False)
        st.markdown(f"""
1. **Inventory > PICS > Empty PICS.**
2. **Inventory > PICS > Import**: kies `{csv_pad.name}`. Import File Type: **Generic CSV - Sku, Quan**. *Reverse Quantity* uit. Klik Import.
3. **Inventory > PICS > PICS Update**: For Location = juiste vestiging, PICS Target Table = **Inventory Table**.
""")
        st.error("Kies bij PICS Update altijd **Append (Add to) Quantities**, nooit Overwrite. Overwrite vervangt de hele voorraad.")
        if regels.afslag_indeling.get("kaas_meenemen"):
            st.warning("Deze lijst bevat ook kaas. Verwerk dezelfde afslag dus **niet** ook nog in het PICS-tool "
                       "(Genereer_PICS_import.xlsm), anders wordt de kaas dubbel geboekt.")


# ---------------------------------------------------------------- hulpjes

def excel_bytes(tabbladen: dict[str, pd.DataFrame]) -> bytes:
    b = io.BytesIO()
    with pd.ExcelWriter(b) as xw:
        for naam, df in tabbladen.items():
            df.to_excel(xw, sheet_name=naam[:31], index=False)
    return b.getvalue()


def nl(x: float, decimalen: int = 3) -> str:
    """1234.5 -> '1.234,500'"""
    return f"{x:,.{decimalen}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def toon_overzicht(t: pd.DataFrame):
    def kleur(rij):
        if rij.Regel == "- bulk":
            return ["background-color: #E1EEF9; font-weight: 600"] * len(rij)
        if rij.Regel == "= totaal":
            ok = rij.Controle == "OK"
            return [f"background-color: {'#EAF7EE' if ok else '#FDEBDD'}; font-style: italic"] * len(rij)
        return [""] * len(rij)
    st.dataframe(t.style.apply(kleur, axis=1).format({"Mutatie": "{:+.3f}", "Van bulk": "{:.3f}", "PLU": "{:.0f}"},
                                                     na_rep=""),
                 hide_index=True, use_container_width=True, height=min(36 * (len(t) + 1), 600),
                 column_config={"Bulk": None, "Bulk-eenheid": None})


# ---------------------------------------------------------------- pagina: voorraad en tellijsten

def pagina_voorraad():
    regels, re_df, koppelingen, _, _ = CTX["bron"]
    uit, paden = CTX["uit"], CTX["paden"]
    st.markdown("## Voorraad & tellijsten")
    stand = datetime.fromtimestamp(paden["re_export"].stat().st_mtime)
    st.caption(f"Voorraad volgens de RE-export `{paden['re_export'].name}` van {stand:%d-%m-%Y %H:%M}. "
               "Wil je de stand van nu? Zet eerst een verse export in de map RE-export op de gedeelde schijf.")
    lijst = voorraad_lijst(re_df, list(koppelingen), regels)

    tab_b, tab_s, tab_sb, tab_t, tab_i = st.tabs(["Bulkvoorraad", "Stuksvoorraad", "Stuksbalans",
                                                  "Tellijst uitdraaien", "Telling inlezen"])
    with tab_sb:
        toon_stuksbalans(stuksbalans_nu(), kort=False)
    for tab, type_ in ((tab_b, BULK), (tab_s, STUK)):
        with tab:
            deel = lijst[lijst.Type == type_]
            c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
            soorten = c1.multiselect("Soort", ["Vlees", "Kaas"], ["Vlees", "Kaas"], key=f"soort_{type_}")
            alleen_neg = c2.checkbox("Alleen negatieve voorraad", key=f"neg_{type_}")
            deel = deel[deel.Soort.isin(soorten)]
            if alleen_neg:
                deel = deel[deel.Voorraad < 0]
            c1, c2, c3 = st.columns(3)
            neg = int((deel.Voorraad < 0).sum())
            kaart(c1, "Artikelen", f"{len(deel)}", f"{neg} met negatieve voorraad", neg == 0)
            kaart(c2, "Voorraad", f"{nl(deel.loc[deel.Eenheid == 'kg', 'Voorraad'].sum())} kg",
                  f"en {nl(deel.loc[deel.Eenheid == 'st', 'Voorraad'].sum(), 0)} stuks")
            kaart(c3, "Waarde", f"$ {nl(deel.Waarde.sum(), 2)}", "voorraad × laatste kostprijs")
            st.write("")
            st.dataframe(deel.drop(columns=["Type"] + (["PLU"] if type_ == BULK else [])), hide_index=True, use_container_width=True, height=480,
                         column_config={"PLU": st.column_config.NumberColumn(format="%d"),
                                        "Voorraad": st.column_config.NumberColumn(format="%.3f"),
                                        "Kostprijs": st.column_config.NumberColumn(format="%.2f"),
                                        "Waarde": st.column_config.NumberColumn(format="%.2f"),
                                        "Gekoppeld": st.column_config.TextColumn("Bulk" if type_ == STUK else "PLU's")})
            st.download_button(f"Download {'bulk' if type_ == BULK else 'stuks'}voorraad (Excel)",
                               excel_bytes({f"{type_}voorraad": deel}),
                               file_name=f"{'Bulk' if type_ == BULK else 'Stuks'}voorraad_{stand:%Y_%m_%d}.xlsx",
                               key=f"dl_{type_}")

    with tab_t:
        st.markdown("Maak een tellijst om te printen. Je collega's vullen per artikel **Geteld** in. "
                    "Lever de ingevulde Excel daarna weer aan bij *Telling inlezen*, of aan Claude.")
        c1, c2 = st.columns(2)
        types = c1.multiselect("Welke lijsten", [BULK, STUK], [BULK, STUK],
                               format_func=lambda t: "Bulk" if t == BULK else "Stuks (porties)")
        soorten = c2.multiselect("Soort", ["Vlees", "Kaas"], ["Vlees", "Kaas"], key="soort_tel")
        toon = st.checkbox("Systeemvoorraad op de lijst zetten", value=False,
                           help="Standaard niet: blind tellen geeft een eerlijkere telling.")
        keuze = lijst[lijst.Type.isin(types) & lijst.Soort.isin(soorten)]
        st.caption(f"{len(keuze)} artikelen: {(keuze.Type == BULK).sum()} bulk, {(keuze.Type == STUK).sum()} stuks. "
                   "Elk soort lijst komt op een eigen tabblad, klaar om te printen.")
        if st.button("Maak tellijst", type="primary", disabled=keuze.empty):
            naam = "_".join(s.lower() for s in soorten)
            pad = vrije_naam(uit / "tellijsten" / f"Tellijst_{naam}_{datetime.now():%Y_%m_%d}.xlsx")
            maak_tellijst(keuze, pad, paden["re_export"].name, toon)
            st.session_state.tellijst = pad
        pad = st.session_state.get("tellijst")
        if pad and Path(pad).exists():
            st.success(f"Opgeslagen: {pad}")
            st.download_button("Download tellijst", Path(pad).read_bytes(), file_name=Path(pad).name)

    with tab_i:
        st.markdown("Kies een ingevulde tellijst. De app vergelijkt **Geteld** met de RE-voorraad op het moment "
                    "van uitdraaien (en toont ook de stand in de huidige RE-export).")
        st.caption("Wat er tussen uitdraaien en tellen is verkocht of geleverd, zit in het verschil. "
                   "Tel daarom kort na het uitdraaien, liefst buiten openingstijd.")
        f = st.file_uploader("Ingevulde tellijst (.xlsx)", type=["xlsx"], key="telling")
        if f is None:
            return
        try:
            t = lees_tellijst(io.BytesIO(f.getvalue()))
        except BronFout as e:
            st.error(str(e))
            return
        v = telverschillen(t, re_df)
        if v.empty:
            st.warning("Er is niets ingevuld bij Geteld.")
            return
        afwijk = v[v.Verschil.fillna(0).abs() > 0.0005]
        totaal = float(v["Waarde verschil"].fillna(0).sum())
        c1, c2, c3 = st.columns(3)
        kaart(c1, "Geteld", f"{len(v)}", f"{t.niet_geteld} niet ingevuld · uitgedraaid {t.info.get('Gemaakt op', '?')}")
        kaart(c2, "Met verschil", f"{len(afwijk)}", "geteld is niet gelijk aan systeem", afwijk.empty)
        kaart(c3, "Waarde verschil", f"$ {nl(totaal, 2)}", "negatief = minder geteld dan in het systeem", totaal >= 0)
        st.write("")
        st.dataframe(v, hide_index=True, use_container_width=True, height=480)
        st.download_button("Download verschillen (Excel)", excel_bytes({"Verschillen": v}),
                           file_name=f"Telverschillen_{datetime.now():%Y_%m_%d_%H%M}.xlsx")


# ---------------------------------------------------------------- pagina: maandcontrole

def pagina_maand():
    regels, re_df, koppelingen, _, _ = CTX["bron"]
    uit = CTX["uit"]
    st.markdown("## Maandcontrole: productie tegen verkoop")
    st.caption("Per artikel: wat de weegschaal heeft geproduceerd (Z-afslag) naast wat RetailEdge heeft verkocht. "
               "Veel meer geproduceerd dan verkocht = er verdwijnt iets (derving, diefstal, verkeerde PLU of scan).")
    with st.expander("Zo maak je de exports", expanded=False):
        st.markdown("""
**Weegschaal:** Z-afslag *Artikelen* over precies dezelfde periode (bijv. de hele maand), of de weekafslagen
die samen die periode dekken. Bestandsnaam zoals `Artikelen_van_20261001_tm_20261031.XLS`.

**RetailEdge:** Reports › **Sales by Items – Grouped by Location**, presets **Summary Report** en
**Department only**. Kies dezelfde periode. Sla op als **Excel File – Data (\\*.xls)**.
Welke afdelingen erin staan maakt niet uit: de app pakt alleen de vlees- en kaasartikelen.
""")
    c1, c2 = st.columns(2)
    z_bestanden = c1.file_uploader("Z-afslag(en) van de weegschaal", type=["xls", "xlsx", "csv"],
                                   accept_multiple_files=True, key="maand_z")
    re_bestanden = c2.file_uploader("Verkoopexport(en) uit RetailEdge (.xls)", type=["xls", "xlsx"],
                                    accept_multiple_files=True, key="maand_re")
    if not z_bestanden or not re_bestanden:
        st.info("Kies links de Z-afslag(en) en rechts de RetailEdge-verkoopexport over dezelfde periode.")
        return

    perioden = [periode_uit_naam(f.name) for f in z_bestanden]
    bekend = [x for x in perioden if x]
    standaard = (min(a for a, _ in bekend), max(b for _, b in bekend)) if bekend else (date.today(), date.today())
    c1, c2 = st.columns(2)
    van = c1.date_input("RE-export: van", standaard[0], format="DD-MM-YYYY")
    tm = c2.date_input("RE-export: t/m", standaard[1], format="DD-MM-YYYY")
    st.caption("De periode staat niet in het RE-bestand zelf: vul in welke periode je in RetailEdge hebt gekozen.")
    for m in controleer_dekking(bekend, van, tm) + [f"{f.name}: periode niet te herkennen." for f, x in
                                                     zip(z_bestanden, perioden) if not x]:
        st.warning(m)

    try:
        bron = uit / "maandcontrole" / "bronnen"
        z = [lees_z_afslag(archiveer(bron, f.name, f.getvalue())) for f in z_bestanden]
        verkoop = pd.concat([lees_re_verkoop(io.BytesIO(f.getvalue())) for f in re_bestanden])
        verkoop = (verkoop.groupby("SKU", as_index=False)
                   .agg({"Omschrijving RE": "first", "Prijs RE": "last", "Handmatig gewogen": "any",
                         "Verkocht": "sum", "Kost": "sum", "Omzet": "sum"}))
    except BronFout as e:
        st.error(str(e))
        return
    drempel = st.slider("Afwijking telt pas mee boven (%)", 0, 25, 5,
                        help="Kleine verschillen (en minder dan 0,5 kg of 0,5 stuk) krijgen status OK.")
    v = vergelijk(z, verkoop, list(koppelingen), regels, re_df, drempel_pct=drempel)
    t = v.tabel

    c1, c2, c3 = st.columns(3)
    kaart(c1, "Geproduceerd (weegschaal)", f"{nl(v.productie_kg)} kg", f"en {nl(v.productie_st, 0)} stuks")
    kaart(c2, "Verkocht (RetailEdge)", f"{nl(v.verkocht_kg)} kg", f"en {nl(v.verkocht_st, 0)} stuks")
    kaart(c3, "Verschil in verkoopwaarde", f"$ {nl(v.waarde_verschil, 2)}",
          "positief = meer geproduceerd dan verkocht", abs(v.waarde_verschil) < 100)
    st.write("")
    statussen = list(t.Status.value_counts().items()) if not t.empty else []
    st.markdown(" · ".join(f"**{n}** {s.lower()}" for s, n in statussen))
    keuze = st.multiselect("Toon status", [s for s, _ in statussen],
                           [s for s, _ in statussen if s != "OK"])
    zicht = t[t.Status.isin(keuze)] if keuze else t
    st.dataframe(zicht, hide_index=True, use_container_width=True, height=520,
                 column_config={"PLU": st.column_config.NumberColumn(format="%d"),
                                "Verschil %": st.column_config.NumberColumn(format="%.1f%%")})
    st.caption("Let op: wat aan het eind van de periode is geproduceerd en pas daarna verkocht wordt (of andersom), "
               "geeft een verschil. Over een hele maand valt dat grotendeels weg. "
               "'Handmatig gewogen' = aan de kassa met de hand gewogen in plaats van met een weegschaal-etiket.")
    naam = f"Maandcontrole_{van:%Y_%m_%d}_tm_{tm:%Y_%m_%d}.xlsx"
    if st.button("Opslaan in uitvoer"):
        pad = vrije_naam(uit / "maandcontrole" / naam)
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_bytes(excel_bytes({"Vergelijking": t}))
        st.success(f"Opgeslagen: {pad}")
    st.download_button("Download (Excel)", excel_bytes({"Vergelijking": t}), file_name=naam)


# ---------------------------------------------------------------- start

CTX: dict = {}


def main():
    inst = laad_instellingen()
    CTX["inst"], CTX["uit"] = inst, uitvoermap(inst)
    pg = st.navigation([
        st.Page(pagina_week, title="Weekverwerking (PICS)", icon="📦", default=True),
        st.Page(pagina_voorraad, title="Voorraad & tellijsten", icon="📋", url_path="voorraad"),
        st.Page(pagina_maand, title="Maandcontrole", icon="📊", url_path="maand"),
    ])
    CTX["bron"], CTX["paden"] = bronnen_zijbalk(inst)
    pg.run()


main()
