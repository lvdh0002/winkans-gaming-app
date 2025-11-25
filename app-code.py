import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import dataframe_image as dfi

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

# --- CSS voor huisstijl en fonts ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');

/* Kopjes in Oswald */
h1, h2, h3, h4, .jde-title {
    font-family: 'Oswald', Arial, sans-serif !important;
    font-weight: 700 !important;
    color: #7A1F1F;
}

/* Body en labels in neutraal font */
html, body, .stApp, .stMarkdown, .stSidebar, .stNumberInput label, .stSelectbox label {
    font-family: 'Segoe UI', 'Aptos', Arial, sans-serif !important;
    font-weight: 400 !important;
}

/* Knoppen */
.stButton>button {
    font-family: 'Oswald', Arial, sans-serif !important;
    font-weight: 700 !important;
    background-color: #7A1F1F;
    color: white;
    border-radius: 6px;
}
.stButton>button:hover {
    background-color: #4B2E2B;
}

/* Huisstijl kleuren */
html, body, .stApp { background-color: #F3E9DB; }
thead tr th { background-color: #C8A165 !important; color: #fff !important; }
.streamlit-expanderHeader { color: #4B2E2B !important; font-weight: 700; }
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #7A1F1F 0%, #4B2E2B 100%);
    color: #fff;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stSelectbox label {
    color: #fff !important;
    font-weight: 400 !important;
}
</style>
""", unsafe_allow_html=True)

# --- Huisstijl kleuren ---
PRIMARY_COLOR = "#7A1F1F"
SECONDARY_BROWN = "#4B2E2B"
ACCENT_BEIGE = "#F3E9DB"
ACCENT_GOLD = "#C8A165"
QUALITY_COLOR = "#2E7D32"
PRICE_COLOR = "#1565C0"
LOGO_PATH = os.path.join("assets", "logo_jde.png")

# --- Titel + Logo ---
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
with col_title:
    st.markdown("<h1 class='jde-title'>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# --- Sidebar: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")

def _sync_from_quality():
    st.session_state.price_input = max(0, 100 - st.session_state.quality_input)

def _sync_from_price():
    st.session_state.quality_input = max(0, 100 - st.session_state.price_input)

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
max_points_criteria = {c: st.sidebar.number_input(f"Max punten {c}", 1, 200, 30) for c in criteria}
max_price_points = st.sidebar.number_input("Max punten Prijs", 1, 200, 40)

st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
verwachte_scores_eigen = {c: float(st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}")) for c in criteria}
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (eigen)", 0.0, 100.0, 10.0, 0.1)

# --- Scenario invoer ---
st.header("📥 Concurrentsituaties")
num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = st.number_input("% duurder dan goedkoopste (conc.)", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}") if not is_cheapest else 0.0
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam": naam, "is_cheapest": is_cheapest, "pct": float(pct), "kval_scores": kval_scores})

# --- Helper functies ---
def score_to_points(s, maxp): return (float(s)/max_scale)*maxp
def compute_quality_points(scores_dict): return sum(score_to_points(scores_dict[c], max_points_criteria[c]) for c in criteria)

def totals_with_margins(jde_margin, comp_margin, jde_quality_pts, comp_quality_pts):
    cheapest = min(jde_margin, comp_margin)
    jde_price_pts = max_price_points * (1 - max(0.0, (jde_margin - cheapest))/100)
    comp_price_pts = max_price_points * (1 - max(0.0, (comp_margin - cheapest))/100)
    return (jde_quality_pts + jde_price_pts, comp_quality_pts + comp_price_pts, jde_price_pts, comp_price_pts)

def find_min_margin_for_win(jde_quality_pts, comp_quality_pts, comp_margin, start_margin, step=0.1):
    current = start_margin
    while current >= 0:
        my_total, comp_total, _, _ = totals_with_margins(current, comp_margin, jde_quality_pts, comp_quality_pts)
        if my_total > comp_total + 0.005:
            return current, start_margin - current
        current = round(current - step, 10)
    return 0.0, start_margin

def best_one_step_quality_gain(current_scores_dict):
    best = None
    for c in criteria:
        cur = float(current_scores_dict[c])
        higher_steps = [x for x in scale_values if float(x) > cur]
        for nxt in higher_steps:
            gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
            if (best is None) or (gain > best[3]):
                best = (c, cur, float(nxt), float(gain))
    return best

# --- Analyse ---
st.header("Resultaten")
if st.button("Bereken winkansen"):
    jde_quality_pts = compute_quality_points(verwachte_scores_eigen)
    overzicht_rows = []
    dashboard_rows = []

    for s in scenarios:
        comp_quality_pts = compute_quality_points(s["kval_scores"])
        comp_margin = 0.0 if s["is_cheapest"] else s["pct"]
        my_total_now, comp_total_now, my_price_now, comp_price_now = totals_with_margins(margin_pct, comp_margin, jde_quality_pts, comp_quality_pts)
        status = "WIN" if my_total_now > comp_total_now else "LOSE" if my_total_now < comp_total_now else "DRAW"
        verschil = round(my_total_now - comp_total_now, 1)

        # Prijsadvies
        target_margin, drop_win = find_min_margin_for_win(jde_quality_pts, comp_quality_pts, comp_margin, margin_pct)
        prijsadvies = f"Verlaag {drop_win:.1f}%-punt (naar {target_margin:.1f}%)" if my_total_now < comp_total_now else "Geen actie nodig"

        # Kwaliteitsadvies
        best_step = best_one_step_quality_gain(verwachte_scores_eigen)
        if best_step:
            c, cur, nxt, gain = best_step
            kwaliteitsadvies = f"Verhoog {c} van {cur}→{nxt} (+{gain:.1f} ptn)"
        else:
            kwaliteitsadvies = "-"

        overzicht_rows.append({
            "Scenario": s["naam"],
            "Status": status,
            "JDE totaal": round(my_total_now,1),
            "JDE prijs": round(my_price_now,1),
            "JDE kwaliteit": round(jde_quality_pts,1),
            "Concurrent totaal": round(comp_total_now,1),
            "Conc prijs": round(comp_price_now,1),
            "Conc kwaliteit": round(comp_quality_pts,1),
            "Verschil": verschil,
            "% duurder": f"{margin_pct:.1f}%" if not s["is_cheapest"] else "Goedkoopste",
            "Prijsactie (%-punt)": prijsadvies,
            "Kwaliteitsadvies": kwaliteitsadvies
        })

        dashboard_rows.append({
            "naam": s["naam"],
            "you_quality": jde_quality_pts,
            "you_price": my_price_now,
            "comp_quality": comp_quality_pts,
            "comp_price": comp_price_now,
            "status": status
        })

    df = pd.DataFrame(overzicht_rows)

    # Kleurcodering
    def color_status(val):
        if val == "WIN": return "background-color: #81C784; color: black;"
        if val == "LOSE": return "background-color: #E57373; color: black;"
        return "background-color: #B0BEC5; color: black;"

    styled_df = df.style.applymap(color_status, subset=["Status"])

    st.subheader("Overzicht alle scenario's")
    st.dataframe(styled_df, use_container_width=True)

    # PNG-download
    img_path = "table.png"
    dfi.export(df.style.applymap(color_status, subset=["Status"]), img_path)
    with open(img_path, "rb") as f:
        st.download_button("📷 Download tabel als afbeelding (PNG)", f, "winkans_tabel.png", "image/png")

    # PDF-download
    if HAS_RL:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="JDETitle", parent=styles["Title"], textColor=colors.HexColor(PRIMARY_COLOR)))
        flow = []
        if os.path.exists(LOGO_PATH): flow.append(Image(LOGO_PATH, width=100, height=48))
        flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["JDETitle"]))
        flow.append(Spacer(1, 12))
        table_data = [list(df.columns)] + df.values.tolist()
        t = Table(table_data)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(ACCENT_GOLD)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey)]))
        flow.append(t)
        doc.build(flow)
        buf.seek(0)
        st.download_button("📄 Download PDF (JDE-stijl)", buf, "advies_winkans.pdf", "application/pdf")
    else:
        st.info("PDF niet beschikbaar (reportlab ontbreekt).")

    # Dashboard-grafiek
    if HAS_MPL:
        fig, ax = plt.subplots(figsize=(10, 0.7*len(dashboard_rows)+2))
        y_you = np.arange(len(dashboard_rows))*2
        y_comp = y_you+0.8
        for i,r in enumerate(dashboard_rows):
            ax.barh(y_you[i],r["you_quality"],color=QUALITY_COLOR)
            ax.barh(y_you[i],r["you_price"],left=r["you_quality"],color=PRICE_COLOR)
            ax.barh(y_comp[i],r["comp_quality"],color="#66BB6A")
            ax.barh(y_comp[i],r["comp_price"],left=r["comp_quality"],color="#42A5F5")
            ax.text(r["you_quality"]+r["you_price"]+0.2,y_you[i],f"{r['you_quality']+r['you_price']:.1f}")
            ax.text(r["comp_quality"]+r["comp_price"]+0.2,y_comp[i],f"{r['comp_quality']+r['comp_price']:.1f}")
            ax.text(0,y_comp[i],r["naam"],va="center",ha="left",color=PRIMARY_COLOR,fontweight="bold")
        ax.set_yticks([])
        ax.set_xlabel("Punten")
        ax.set_title("Dashboard: overzicht per scenario",color=PRIMARY_COLOR)
        st.pyplot(fig)
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
