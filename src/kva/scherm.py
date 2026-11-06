"""Scherm (Streamlit) met stappenplan voor de wekelijkse voorraadcorrectie.

Starten: dubbelklik start_scherm.cmd, of: python -m streamlit run src/kva/scherm.py
"""

from __future__ import annotations

import sys
from datetime import datetime
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
    BUITEN, KAAS, ONBEKEND, VLEES, VLEES_GEEN_BULK, controleer_periode, deel_in,
    mapping_uit_koppeling, pics_regels, totaalcontrole,
)

st.set_page_config(page_title="Voorraadcorrectie vlees", page_icon="🥩", layout="wide")

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
    k = koppel(lees_weegschaal(Path(weeg_pad)), re_df, regels)
    tool = lees_mappingtabel(Path(tool_pad), regels.pics_menu_tabblad)
    kaas = Mapping(regels={p: m for p, m in tool.regels.items() if m.tabblad == "Kaas"})
    namen = dict(zip(k.bulks.Inv_Sku, k.bulks.Inv_Desc))
    return regels, re_df, k, kaas, namen


def bronnen_zijbalk(inst):
    st.sidebar.header("Bronnen")
    paden = {}
    try:
        for sleutel, naam in (("re_export", "RE-export"), ("weegschaal", "Weegschaal-lijst"), ("pics_tool", "PICS-tool (kaas)")):
            p = zoek_bestand(inst["bronnen"][sleutel])
            paden[sleutel] = p
            dagen = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).days
            st.sidebar.markdown(f"**{naam}**  \n{p.name}  \n_{dagen} dagen oud_")
            if sleutel == "re_export" and dagen > 7:
                st.sidebar.warning("RE-export is ouder dan een week. Zet een verse export in de map voor de beste controle.")
    except BronFout as e:
        st.sidebar.error(str(e))
        st.stop()
    bron = laad_bronnen(*(x for k in ("re_export", "weegschaal", "pics_tool")
                          for x in (str(paden[k]), paden[k].stat().st_mtime)))
    k = bron[2]
    st.sidebar.markdown(f"Vlees-PLU's: **{k.aantal}**, gekoppeld **{k.gekoppeld}**, open **{k.open}**")
    if st.sidebar.button("Bronnen opnieuw inlezen"):
        laad_bronnen.clear()
        st.rerun()
    return bron


def kop(nummer: int, titel: str, klaar: bool):
    st.subheader(f"{'✅' if klaar else '⬜'} Stap {nummer}: {titel}")


# ---------------------------------------------------------------- pagina

def main():
    inst = laad_instellingen()
    uit = uitvoermap(inst)
    regels, re_df, k, kaas, bulk_namen = bronnen_zijbalk(inst)
    ss = st.session_state

    st.title("Voorraadcorrectie vlees (PICS)")
    st.caption("Wekelijks: Z-afslag van de weegschaal inlezen, controleren en een PICS-lijst maken voor RetailEdge.")

    # ---------------- stap 1
    with st.container(border=True):
        kop(1, "Upload de Z-afslag van afgelopen week (maandag t/m zondag)", ss.get("upload") is not None)
        bestand = st.file_uploader("Z-afslag van de hele weegschaal (.XLS, .xlsx of .csv)",
                                   type=["xls", "xlsx", "csv"], key="upload")
        if bestand is None:
            for s in ("tabel", "afslag", "pics", "opgeslagen"):
                ss.pop(s, None)
            st.info("Kies het bestand `Artikelen_van_..._tm_....XLS` uit de map Z-afslagen.")
            st.stop()

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
        kol = st.columns(5)
        for c, cat in zip(kol, (VLEES, VLEES_GEEN_BULK, KAAS, BUITEN, ONBEKEND)):
            c.metric(cat, int(tel.get(cat, 0)))

        for naam, ok, tekst_ in totaalcontrole(ind, regels.afslag_indeling.get("totaal_tolerantie", 0.01)):
            (st.success if ok else st.error)(f"Totaalcontrole {naam}: {tekst_} → {'OK' if ok else 'VERSCHIL, controleer de afslag'}")
        for m in ind.overgeslagen:
            st.info(m)

        st.markdown(
            "Hieronder per regel wat er gebeurt. **Meenemen** = komt in de PICS-lijst. "
            "Je kunt aanpassen: meenemen aan/uit, hoeveelheid, portie ART NR, bulk SKU en hoeveel er van de bulk "
            "afgaat (in kg). Kaas staat standaard uit, omdat die via het PICS-tool loopt.")
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


main()
