"""Scherm (Streamlit) met stappenplan voor de wekelijkse voorraadcorrectie.

Starten: dubbelklik start_scherm.cmd, of: python -m streamlit run src/kva/scherm.py
"""

from __future__ import annotations

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
    mapping_uit_koppeling, pics_regels, totaalcontrole,
)

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
    st.sidebar.markdown("### Bronbestanden")
    st.sidebar.caption("De app pakt steeds het nieuwste bestand uit de map `data`.")
    paden = {}
    try:
        for sleutel, naam in (("re_export", "RE-export"), ("weegschaal", "Weegschaal-lijst"), ("pics_tool", "PICS-tool (kaas)")):
            p = zoek_bestand(inst["bronnen"][sleutel])
            paden[sleutel] = p
            d = dagen_oud(p)
            oud = sleutel == "re_export" and d > 7
            st.sidebar.markdown(f"{'🟠' if oud else '🟢'} **{naam}**  \n<small>{p.name} · "
                                f"{'vandaag' if d == 0 else f'{d} dagen oud'}</small>", unsafe_allow_html=True)
            if oud:
                st.sidebar.warning("De RE-export is ouder dan een week. Zet een verse export in de map.")
    except BronFout as e:
        st.sidebar.error(str(e))
        st.stop()
    bron = laad_bronnen(*(x for k in ("re_export", "weegschaal", "pics_tool")
                          for x in (str(paden[k]), paden[k].stat().st_mtime)))
    if st.sidebar.button("Bronnen opnieuw inlezen", use_container_width=True):
        laad_bronnen.clear()
        st.rerun()
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


def voorblad(koppelingen, paden, uit: Path):
    """Overzicht voordat er een bestand is gekozen: welke week, staat alles klaar, wat is al gedaan."""
    van, tm = vorige_week()
    verwacht = f"Artikelen_van_{van:%Y%m%d}_tm_{tm:%Y%m%d}"
    log = sorted(lees_log(uit).values(), key=lambda r: r["datum"], reverse=True)
    al_gedaan = next((r for r in log if r["bestand"].startswith(verwacht)), None)

    c1, c2, c3 = st.columns(3)
    if al_gedaan:
        kaart(c1, "Deze week", "Al verwerkt ✓", f"{datum_kort(van)} t/m {datum_kort(tm)}, op {al_gedaan['datum']}")
    else:
        kaart(c1, "Te verwerken", f"{datum_kort(van)} – {datum_kort(tm)}", f"Bestand: <code>{verwacht}.XLS</code>")
    for kol, k in zip((c2, c3), koppelingen):
        ok = k.open == 0
        kaart(kol, f"{k.soort.capitalize()}: koppeling", f"{k.gekoppeld} van {k.aantal}",
              "Alle PLU's hebben een bulk." if ok else f"{k.open} PLU's zonder bulk: die worden niet afgeboekt.", ok)
    re_oud = dagen_oud(paden["re_export"])
    if re_oud > 7:
        st.warning(f"De RE-export is {re_oud} dagen oud. Zet eerst een verse export in `data\\re_export`.")
    st.write("")
    return log


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

def main():
    inst = laad_instellingen()
    uit = uitvoermap(inst)
    (regels, re_df, (k, k_kaas), kaas, bulk_namen), paden = bronnen_zijbalk(inst)
    ss = st.session_state

    koptekst()
    huidig = 4 if "opgeslagen" in ss else 3 if "pics" in ss else 2 if ss.get("upload") is not None else 1
    stappenbalk(huidig)

    # ---------------- stap 1
    if ss.get("upload") is None:
        log = voorblad((k, k_kaas), paden, uit)
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
        eerder = lees_log(uit).get(h)
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
        c1, c2, c3 = st.columns(3)
        c1.metric("Portie-artikelen (+)", len(lijst.porties))
        c2.metric("Bulk-artikelen (−)", len(lijst.bulks))
        c3.metric("Afgeboekt van bulk", formatteer(-sum(lijst.bulks.values(), start=0)))
        with st.expander(f"Bekijk de {len(lijst.regels)} regels"):
            st.dataframe(pd.DataFrame([r.split(",") for r in lijst.regels], columns=["SKU", "Hoeveelheid"]),
                         hide_index=True)

        if "opgeslagen" not in ss:
            if st.button("Opslaan"):
                stam = Path(ss.afslag["naam"]).stem
                csv_pad = vrije_naam(uit / f"{stam}_PICS_import.csv")
                with open(csv_pad, "w", encoding="ascii", newline="\r\n") as f:
                    f.write("\n".join(lijst.regels) + "\n")
                tabel.to_excel(vrije_naam(uit / f"{stam}_verwerking.xlsx"), index=False)
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


main()
