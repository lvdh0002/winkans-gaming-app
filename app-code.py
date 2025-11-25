import streamlit as st
import pandas as pd
import numpy as np
import io
import os

# --- Robust imports ---
HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except Exception:
    HAS_MPL = False

HAS_RL = True
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.utils import ImageReader
except Exception:
    HAS_RL = False

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
st.title("Tool om winkansen te berekenen o.b.v. de BPKV-methode (Beste Prijs Kwaliteit Verhouding)")

# --- JDE Huisstijl ---
PRIMARY_COLOR = "#8B0000"   # Diep rood
SECONDARY_BROWN = "#5A3A29" # Koffiebruin
ACCENT_BEIGE = "#E8D7C1"    # Beige
ACCENT_GOLD  = "#C0A060"    # Goudaccent
QUALITY_COLOR = "#4CAF50"   # Groen voor kwaliteit
PRICE_COLOR   = "#2196F3"   # Blauw voor prijs
LOGO_PATH = os.path.join("assets", "logo_jde.png")

# Custom CSS
st.markdown(f"""
<style>
html, body, .stApp {{
  background-color: #FAF7F2;
  font-family: Arial, Helvetica, sans-serif;
}}
h1, h2, h3, h4 {{
  color: {PRIMARY_COLOR};
}}
.stButton>button {{
  background-color: {PRIMARY_COLOR};
  color: white;
  border-radius: 6px;
}}
.stButton>button:hover {{
  background-color: {SECONDARY_BROWN};
}}
thead tr th {{
  background-color: {ACCENT_BEIGE} !important;
  color: {SECONDARY_BROWN} !important;
}}
</style>
""", unsafe_allow_html=True)

# Logo
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=140)

# --- Sidebar: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")

def _sync_from_quality():
    st.session_state.price_input = 100 - st.session_state.quality_input

def _sync_from_price():
    st.session_state.quality_input = 100 - st.session_state.price_input

col1, col2 = st.sidebar.columns(2)
with col1:
    st.number_input("Kwaliteit (%)", 0, 100, 60, 1, key="quality_input", on_change=_sync_from_quality)
with col2:
    st.number_input("Prijs (%)", 0, 100, 40, 1, key="price_input", on_change=_sync_from_price)

kwaliteit_pct = st.session_state.quality_input
prijs_pct = st.session_state.price_input
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_pct}%  \n- **Prijs:** {prijs_pct}%")

# --- Puntenschaal ---
st.sidebar.subheader("Puntenschaal")
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-2,5-5-7,5-10": [0,2.5,5,7.5,10],
    "0%-20%-40%-60%-80%-100%": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "0-30-50-80-100": [0,30,50,80,100],
    "0-30-50-70": [0,30,50,70],
    "Custom...": None
}
scale_label = st.sidebar.selectbox("Kies een schaal", list(scales.keys()))
if scale_label == "Custom...":
    vals = st.sidebar.text_input("Eigen schaal (komma-gescheiden)", "0,25,50,75,100")
    try:
        scale_values = [float(x) for x in vals.split(",")]
    except:
        st.sidebar.error("Ongeldige schaal.")
        scale_values = [0,25,50,75,100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

criteria = [c.strip() for c in st.sidebar.text_input("Criterianamen (komma)", "Kwaliteit,Service").split(",") if c.strip()]
max_points_criteria = {c: st.sidebar.number_input(f"Max punten {c}", 1, 100, 60) for c in criteria}
max_price_points = st.sidebar.number_input("Max punten Prijs", 1, 100, 40)

st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
verwachte_scores_eigen = {c: float(st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}")) for c in criteria}
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste", 0.0, 100.0, 10.0, 0.1)
eigen_prijs_points = max_price_points * (1 - margin_pct/100)
st.sidebar.markdown(f"**Eigen Prijsscore:** {eigen_prijs_points:.1f}")

# --- Scenario invoer ---
st.header("📥 Concurrentsituaties")
num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = st.number_input("% duurder dan goedkoopste", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}") if not is_cheapest else 0.0
        prijs_pts = max_price_points * (1 if is_cheapest else 1 - pct/100)
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam": naam, "prijs_pts": prijs_pts, "kval_scores": kval_scores})

# --- Helper functies ---
def score_to_points(s, maxp, max_scale): return (float(s)/max_scale)*maxp
def price_route_for_win(comp_total, your_quality_pts, max_price_points, current_margin_pct):
    required_price_points = (comp_total + 0.01) - your_quality_pts
    if required_price_points > max_price_points: return 0.0, current_margin_pct, False
    target_margin_pct = 100*(1 - required_price_points/max_price_points)
    return target_margin_pct, current_margin_pct - target_margin_pct, True

# --- Analyse & Resultaten ---
st.header("Resultaten")
if st.button("Bereken winkansen"):
    jde_quality_pts = sum(score_to_points(verwachte_scores_eigen[c], max_points_criteria[c], max_scale) for c in criteria)
    jde_price_pts = eigen_prijs_points
    jde_total = jde_quality_pts + jde_price_pts

    overzicht_rows = []
    wins_no_action = wins_via_price = wins_via_quality = wins_via_combo = not_feasible = 0

    for s in scenarios:
        comp_quality_pts = sum(score_to_points(s['kval_scores'][c], max_points_criteria[c], max_scale) for c in criteria)
        comp_price_pts = s['prijs_pts']
        comp_total = comp_quality_pts + comp_price_pts
        status = "WIN" if jde_total > comp_total else "LOSE" if jde_total < comp_total else "DRAW"
        icon = "✅" if status=="WIN" else "❌" if status=="LOSE" else "⚠️"
        st.markdown(f"### {icon} {s['naam']} — {status}")
        st.write(f"**Jouw totaalscore:** {jde_total:.1f} | **Concurrent:** {comp_total:.1f}")

        qual_hint = ""
        price_drop_txt = ""
        if status == "WIN":
            wins_no_action += 1
            st.success("Je wint zonder actie.")
        else:
            target_margin_pct, drop_win, feasible = price_route_for_win(comp_total, jde_quality_pts, max_price_points, margin_pct)
            if feasible and drop_win > 0:
                st.warning(f"**Prijs-route:** verlaag prijs met **{drop_win:.1f} %-punt** (naar {target_margin_pct:.1f}%).")
                wins_via_price += 1
                price_drop_txt = f"{drop_win:.1f} (naar {target_margin_pct:.1f}%)"
            else:
                st.info("Prijs-route niet haalbaar, kijk naar kwaliteit.")
            # Kwaliteit-route check
            gap = comp_total - jde_total
            suggestion = None
            for c in criteria:
                current = verwachte_scores_eigen[c]
                for nxt in [n for n in scale_values if n > current]:
                    gain = score_to_points(nxt, max_points_criteria[c], max_scale) - score_to_points(current, max_points_criteria[c], max_scale)
                    if gain >= gap + 0.01:
                        suggestion = (c, current, nxt, gain)
                        break
                if suggestion: break
            if suggestion:
                c, cur, nxt, gain = suggestion
                st.info(f"**Kwaliteit-route:** verhoog {c} van {cur} naar {nxt} (+{gain:.1f} ptn).")
                qual_hint = f"{c}: {cur}→{nxt}"
                wins_via_quality += 1
            else:
                st.info("Geen simpele kwaliteitsstap mogelijk.")
                not_feasible += 1

        overzicht_rows.append({"Scenario": s["naam"], "JDE (totaal)": round(jde_total,1), "Concurrent (totaal)": round(comp_total,1), "Status": status, "Prijsactie": price_drop_txt, "Kwaliteitsadvies": qual_hint})

    df_overzicht = pd.DataFrame(overzicht_rows).set_index("Scenario")
    st.subheader("Overzicht")
    st.dataframe(df_overzicht)

    st.subheader("Samenvatting")
    st.markdown(f"""
- Zonder actie win je in **{wins_no_action}** scenario's.
- Via prijs: **{wins_via_price}** scenario's.
- Via kwaliteit: **{wins_via_quality}** scenario's.
- Niet haalbaar met simpele acties: **{not_feasible}** scenario's.
    """)

    csv = df_overzicht.to_csv()
    st.download_button("Download CSV", csv, "winkans_overzicht.csv")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
