
import streamlit as st
import pandas as pd
import numpy as np
import math
import io
import os

# --- Optional imports for dashboard / PDF ---
HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except Exception:
    HAS_MPL = False

HAS_RL = True
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.utils import ImageReader
except Exception:
    HAS_RL = False

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

# --- JDE Huisstijl CSS ---
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

/* Kleuren */
html, body, .stApp { background-color: #F3E9DB; }
thead tr th { background-color: #C8A165 !important; color: #fff !important; }
.streamlit-expanderHeader { color: #4B2E2B !important; font-weight: 700; }

/* Sidebar headerband (stabiel wijnrood) */
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
PRICE_COLOR   = "#1565C0"
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
        st.sidebar.error("Ongeldige schaal (komma-gescheiden getallen).")
        scale_values = [0,25,50,75,100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

criteria = [c.strip() for c in st.sidebar.text_input("Criterianamen (komma, min 2)", "Kwaliteit,Service").split(",") if c.strip()]
if len(criteria) < 2:
    st.sidebar.error("Voeg minstens 2 criteria toe.")
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
        scenarios.append({"naam": naam, "pct": float(pct), "kval_scores": kval_scores})

# --- Helper functies ---
def score_to_points(s, maxp): 
    return (float(s) / float(max_scale)) * float(maxp)

def compute_quality_points(scores_dict):
    return sum(score_to_points(scores_dict[c], max_points_criteria[c]) for c in criteria)

def price_points_from_margins(my_margin, comp_margin):
    """
    Relatieve prijspunten t.o.v. de goedkoopste binnen dit scenario (jij vs. 1 concurrent).
    """
    cheapest = min(my_margin, comp_margin)
    my_rel = max(0.0, my_margin - cheapest)
    comp_rel = max(0.0, comp_margin - cheapest)
    my_price_pts = max_price_points * (1.0 - my_rel / 100.0)
    comp_price_pts = max_price_points * (1.0 - comp_rel / 100.0)
    return my_price_pts, comp_price_pts

def minimal_drop_for_win(my_margin, comp_margin, jde_quality_pts, comp_quality_pts, max_price_points):
    """
    Gesloten-formule: je wint als m < comp_margin + (100/M)*Qgap, met Qgap = JDE_quality - CONC_quality.
    Geeft: (target_margin, drop_int) waarbij drop_int = ceil(benodigde %-punt daling), cap bij 0%.
    """
    M = float(max_price_points)
    Qgap = float(jde_quality_pts - comp_quality_pts)
    threshold = comp_margin + (100.0 / M) * Qgap  # marge waarbij je net wint
    # Benodigde daling (naar max(0, threshold))
    needed = max(0.0, my_margin - max(0.0, threshold))
    drop_int = int(math.ceil(needed))
    target_margin = max(0.0, my_margin - drop_int)
    return target_margin, drop_int

def best_one_step_quality_gain(current_scores_dict, jde_quality_pts, comp_total_now):
    """
    Vind de kleinste volgende stap per criterium die direct WIN oplevert, anders de beste stap overall.
    Return: (criterium, cur, nxt, gain)
    """
    # 1) Probeer per criterium de eerste stap die tot winst leidt
    for c in criteria:
        cur = float(current_scores_dict[c])
        higher_steps = [x for x in scale_values if float(x) > cur]
        for nxt in higher_steps:
            gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
            if (jde_quality_pts + gain) > comp_total_now + 0.005:
                return (c, cur, float(nxt), float(gain))
    # 2) Anders: beste stap (max gain)
    best = None
    for c in criteria:
        cur = float(current_scores_dict[c])
        higher_steps = [x for x in scale_values if float(x) > cur]
        for nxt in higher_steps:
            gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
            if (best is None) or (gain > best[3]):
                best = (c, cur, float(nxt), float(gain))
    return best

# --- Analyse & Output ---
st.header("Resultaten")

if st.button("Bereken winkansen"):
    jde_quality_pts = compute_quality_points(verwachte_scores_eigen)

    overzicht_rows = []
    dashboard_rows = []

    for s in scenarios:
        comp_margin = float(s["pct"])
        comp_quality_pts = compute_quality_points(s["kval_scores"])

        # Huidige prijspunten (relatief aan huidig goedkoopste tussen jou en deze concurrent)
        my_price_now, comp_price_now = price_points_from_margins(margin_pct, comp_margin)
        my_total_now = jde_quality_pts + my_price_now
        comp_total_now = comp_quality_pts + comp_price_now

        status = "WIN" if my_total_now > comp_total_now else ("LOSE" if my_total_now < comp_total_now else "DRAW")
        verschil = int(round(my_total_now - comp_total_now))

        # Concreet prijsadvies (altijd integer %-punt, naar boven afgerond)
        target_margin, drop_int = minimal_drop_for_win(margin_pct, comp_margin, jde_quality_pts, comp_quality_pts, max_price_points)
        if status == "WIN" or drop_int <= 0:
            prijsactie = "Geen actie nodig"
        else:
            prijsactie = f"Verlaag {drop_int}%-punt (naar {int(round(target_margin))}%)"

        # Kwaliteitsactie (toon concrete eerstvolgende stap die WIN oplevert; anders beste stap overall)
        qual_step = best_one_step_quality_gain(verwachte_scores_eigen, jde_quality_pts, comp_total_now)
        if qual_step:
            c, cur, nxt, gain = qual_step
            kwaliteitsactie = f"Verhoog {c} van {int(round(cur))}→{int(round(nxt))} (+{int(round(gain))} ptn)"
        else:
            kwaliteitsactie = "-"

        overzicht_rows.append({
            "Scenario": s["naam"],
            "Status": status,
            "JDE totaal": int(round(my_total_now)),
            "JDE prijs": int(round(my_price_now)),
            "JDE kwaliteit": int(round(jde_quality_pts)),
            "Concurrent totaal": int(round(comp_total_now)),
            "Conc prijs": int(round(comp_price_now)),
            "Conc kwaliteit": int(round(comp_quality_pts)),
            "Verschil": verschil,
            "% duurder (JDE)": f"{int(round(margin_pct))}%" if margin_pct > 0 else "Goedkoopste",
            "% duurder (Conc)": f"{int(round(comp_margin))}%" if comp_margin > 0 else "Goedkoopste",
            "Prijsactie": prijsactie,
            "Kwaliteitsactie": kwaliteitsactie
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

    # Kleurcodering (WIN=groen, LOSE=rood, DRAW=grijs)
    def color_status(val):
        if val == "WIN": return "background-color: #81C784; color: black;"
        if val == "LOSE": return "background-color: #E57373; color: black;"
        return "background-color: #B0BEC5; color: black;"

    st.subheader("Overzicht alle scenario's")
    st.dataframe(df.style.applymap(color_status, subset=["Status"]), use_container_width=True)

    # CSV-download
    st.download_button("Download CSV", df.to_csv(index=False), "winkans_overzicht.csv", "text/csv")

    # PDF (landscape, one-pager) in JDE-stijl
    if HAS_RL:
        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buf,
            pagesize=landscape(A4),  # LANDSCAPE!
            leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="JDETitle", parent=styles["Title"], textColor=colors.HexColor(PRIMARY_COLOR)))
        styles.add(ParagraphStyle(name="JDENormal", parent=styles["Normal"], textColor=colors.black))

        flow = []
        if os.path.exists(LOGO_PATH):
            flow.append(Image(LOGO_PATH, width=120, height=58))
            flow.append(Spacer(1, 6))
        flow.append(Paragraph("Advies: Winkans & Acties (BPKV) — One pager", styles["JDETitle"]))
        flow.append(Spacer(1, 8))

        # Bouw tabeldata (zonder decimalen)
        columns = [
            "Scenario", "Status",
            "JDE totaal", "JDE prijs", "JDE kwaliteit",
            "Concurrent totaal", "Conc prijs", "Conc kwaliteit",
            "Verschil",
            "% duurder (JDE)", "% duurder (Conc)",
            "Prijsactie", "Kwaliteitsactie"
        ]
        table_data = [columns] + df[columns].values.tolist()

        # Tabel met kolombreedtes zodat alles past op landscape A4
        col_widths = [
            80, 60, 70, 60, 80, 90, 70, 80, 60, 90, 90, 130, 160
        ]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(ACCENT_GOLD)),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F2EA")])
        ]))
        flow.append(t)
        flow.append(Spacer(1, 8))

        # Optioneel: korte samenvatting (aantal WIN/LOSE/DRAW)
        wins = (df["Status"] == "WIN").sum()
        draws = (df["Status"] == "DRAW").sum()
        losses = (df["Status"] == "LOSE").sum()
        flow.append(Paragraph(f"Wins: {wins} • Draws: {draws} • Losses: {losses}", styles["JDENormal"]))

        doc.build(flow)
        pdf_buf.seek(0)
        st.download_button("📄 Download PDF (JDE-stijl, landscape one-pager)", pdf_buf, "advies_winkans_jde.pdf", "application/pdf")
    else:
        st.info("PDF niet beschikbaar (reportlab ontbreekt). Voeg 'reportlab' toe aan requirements.txt en redeploy.")

    # Dashboard (optioneel)
    if HAS_MPL:
        st.subheader("📊 Dashboard-grafiek (alle scenario's)")
        n = len(dashboard_rows)
        fig, ax = plt.subplots(figsize=(10, 0.7*n + 2))
        y_you = np.arange(n)*2
        y_comp = y_you + 0.8
        for i, r in enumerate(dashboard_rows):
            # Jij
            ax.barh(y_you[i], r["you_quality"], color=QUALITY_COLOR, label="Kwaliteit (Jij)" if i == 0 else None)
            ax.barh(y_you[i], r["you_price"], left=r["you_quality"], color=PRICE_COLOR, label="Prijs (Jij)" if i == 0 else None)
            # Concurrent
            ax.barh(y_comp[i], r["comp_quality"], color="#66BB6A", label="Kwaliteit (Conc)" if i == 0 else None)
            ax.barh(y_comp[i], r["comp_price"], left=r["comp_quality"], color="#42A5F5", label="Prijs (Conc)" if i == 0 else None)
            # Labels
            ax.text(r["you_quality"] + r["you_price"] + 0.2, y_you[i], f"{int(round(r['you_quality'] + r['you_price']))}", va="center", color=SECONDARY_BROWN, fontsize=9)
            ax.text(r["comp_quality"] + r["comp_price"] + 0.2, y_comp[i], f"{int(round(r['comp_quality'] + r['comp_price']))}", va="center", color=SECONDARY_BROWN, fontsize=9)
            ax.text(0, y_comp[i], r["naam"], va="center", ha="left", color=PRIMARY_COLOR, fontweight="bold", fontsize=10)
        ax.set_yticks([])
        ax.set_xlabel("Punten", color=SECONDARY_BROWN)
        ax.set_title("Dashboard: overzicht per scenario", color=PRIMARY_COLOR)
        ax.grid(axis="x", alpha=0.25)
        ax.legend(loc="upper right")
        st.pyplot(fig)
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
