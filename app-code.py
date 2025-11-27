import streamlit as st
import pandas as pd
import math
import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

# ============ JDE PAGE STYLING ============

st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');

h1, h2, h3, h4 {
    font-family: 'Oswald', sans-serif !important;
    font-weight: 700;
    color: #7A1F1F;
}

html, body, .stApp {
    background-color: #F3E9DB;
    font-family: 'Segoe UI', sans-serif !important;  /* Aptos-look */
    color: #000;
}

.stButton>button {
    font-family: 'Oswald', sans-serif !important;
    font-weight: 700;
    background: #7A1F1F;
    color: #fff;
    border-radius: 6px;
}

.stButton>button:hover {
    background: #4B2E2B;
}

[data-testid="stSidebar"] > div:first-child {
    background: #A13D3B !important;
    color: #fff !important;
}

[data-testid="stSidebar"] label {
    color: #fff !important;
}
</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"
ACCENT_GOLD = "#C8A165"
PAGE_BEIGE = "#F3E9DB"

LOGO_PATH = os.path.join("assets", "logo_jde.png")

# ==========================================

if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=120)

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# ============ SIDEBAR SETTINGS ============

st.sidebar.header("Stap 1: Beoordelingsmethodiek")

# Prijs + kwaliteit = 100
prijs_pct = st.sidebar.slider("Prijs (%)", 0, 100, 40)
kwaliteit_pct = 100 - prijs_pct
st.sidebar.markdown(f"**Kwaliteit (%)**: {kwaliteit_pct} (automatisch)")

# Schalen
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-20-40-60-80-100": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "Custom...": None
}

scale_label = st.sidebar.selectbox("Kies een schaal", list(scales.keys()))
if scale_label != "Custom...":
    scale_values = scales[scale_label]
else:
    raw = st.sidebar.text_input("Custom schaal (comma separated)", "0,25,50,75,100")
    try:
        scale_values = [float(x.strip()) for x in raw.split(",") if x.strip()]
    except:
        st.sidebar.error("Ongeldige schaal — standaard toegepast.")
        scale_values = [0,25,50,75,100]

max_scale = max(scale_values)

# Criteria
criteria = [c.strip() for c in st.sidebar.text_input("Criterianamen", "Duurzaamheid,Service").split(",") if c.strip()]
max_points_criteria = {c: st.sidebar.number_input(f"Max punten {c}", 1, 200, 30, key=f"max_{c}") for c in criteria}
max_price_points = st.sidebar.number_input("Max punten Prijs", 1, 200, 40)

# JDE scores
verwachte_scores_eigen = {}
for c in criteria:
    sel = st.sidebar.selectbox(f"Score {c} (JDE)", [str(x) for x in scale_values])
    try:
        verwachte_scores_eigen[c] = float(sel)
    except:
        verwachte_scores_eigen[c] = 0

margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (JDE)", 0.0, 100.0, 10.0, 0.1)

# ============ SCENARIOS ============

st.header("📥 Concurrentsituaties")

num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []

for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")

        marge = 0 if cheapest else st.number_input("% duurder dan goedkoopste", 0.0, 100.0, margin_pct, 0.1, key=f"m{i}")

        kval_scores = {}
        for c in criteria:
            sel = st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"s_{i}_{c}")
            kval_scores[c] = float(sel)

        scenarios.append({"naam": naam, "marge": marge, "kval_scores": kval_scores})

# ============ HELPERS ============

def score_to_points(score, max_points):
    return (float(score) / max_scale) * max_points

def compute_quality_points(scores):
    return sum(score_to_points(scores[c], max_points_criteria[c]) for c in criteria)

def absolute_price_points(marge, maxp):
    return maxp * (1 - marge / 100)

def required_drop_piecewise(my_m, comp_m, Qm, Qc, M):
    try:
        mA = comp_m + (100 / M) * (Qm - Qc)
        mB = comp_m - (100 / M) * (Qc - Qm)
        m_req = mA if mA >= comp_m else mB
        drop = max(0, my_m - m_req)
        drop_int = int(math.ceil(drop))
        target = int(round(my_m - drop_int))
        return drop_int, target
    except:
        return 0, int(my_m)

def advice_route(price, quality):
    if "Verlaag" in price and "Verhoog" in quality:
        return "Adviesroute: prijs + kwaliteit"
    if "Verlaag" in price:
        return "Adviesroute: prijs"
    if "Verhoog" in quality:
        return "Adviesroute: kwaliteit"
    return "Adviesroute: geen actie"

# ============ BEREKENING ============

st.header("Resultaten")

if st.button("Bereken winkansen"):

    jde_q = compute_quality_points(verwachte_scores_eigen)
    jde_p = absolute_price_points(margin_pct, max_price_points)
    jde_total = jde_q + jde_p

    rows = []

    for idx, s in enumerate(scenarios, start=1):

        comp_q = compute_quality_points(s["kval_scores"])
        comp_p = absolute_price_points(s["marge"], max_price_points)
        comp_total = comp_q + comp_p

        if jde_total > comp_total:
            status = "WIN"
        elif jde_total < comp_total:
            status = "LOSE"
        else:
            status = "DRAW"

        verschil = int(round(jde_total - comp_total))

        drop, target = required_drop_piecewise(margin_pct, s["marge"], jde_q, comp_q, max_price_points)
        prijsactie = "Geen actie nodig" if status == "WIN" else f"Verlaag {drop}% → {target}%"

        # Kwaliteitsactie
        qual_act = "-"
        if status != "WIN":
            for c in criteria:
                cur = verwachte_scores_eigen[c]
                higher = [x for x in scale_values if x > cur]
                for nxt in higher:
                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                    if jde_q + gain + jde_p > comp_total:
                        qual_act = f"Verhoog {c} {int(cur)} → {int(nxt)} (+{int(gain)}p)"
                        break
                if qual_act != "-":
                    break
            if qual_act == "-":
                qual_act = "Ontoereikend"

        rows.append({
            "Scenario": s["naam"],
            "Status": status,
            "Verschil": verschil,
            "JDE totaal": int(jde_total),
            "JDE kwaliteit": round(jde_q, 2),
            "JDE prijs": round(jde_p, 2),
            "Conc totaal": int(comp_total),
            "Conc kwaliteit": round(comp_q, 2),
            "Conc prijs": round(comp_p, 2),
            "Prijsactie": prijsactie,
            "Kwaliteitsactie": qual_act
        })

    df = pd.DataFrame(rows)

    st.subheader("Volledige tabel (met kwaliteit- en prijspunten)")
    st.dataframe(df, use_container_width=True)

    # ============ PDF EXPORT ============

    pdf = io.BytesIO()

    doc = SimpleDocTemplate(pdf, pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle("JDETitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor(PRIMARY_COLOR),
        leading=24,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle("JDENormal",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.black,
        leading=14
    ))
    styles.add(Paragraph
        ("JDEItalic",
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=colors.HexColor("#444"),
    ))

    flow = []

    if os.path.exists(LOGO_PATH):
        flow.append(Image(LOGO_PATH, width=100, height=40))
        flow.append(Spacer(1, 8))

    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["JDETitle"]))
    flow.append(Spacer(1, 12))

    # JDE summary
    jde_scores = ", ".join([f"{c}: {int(verwachte_scores_eigen[c])}" for c in criteria])
    flow.append(Paragraph(f"<b>JDE:</b> {margin_pct}% duurder, scores: {jde_scores}", styles["JDENormal"]))
    flow.append(Spacer(1, 10))

    # Table (compact)
    pdf_cols = ["Scenario", "Status", "Verschil", "Prijsactie", "Kwaliteitsactie"]
    table_data = [pdf_cols] + [[r[c] for c in pdf_cols] for r in rows]

    table = Table(table_data, colWidths=[120, 70, 60, 150, 150])
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(0,0),(-1,-1),'CENTER')
    ]))

    flow.append(table)
    flow.append(Spacer(1, 14))

    # Routes
    flow.append(Paragraph("<b>Adviesroutes:</b>", styles["JDENormal"]))
    for r in rows:
        route = advice_route(r["Prijsactie"], r["Kwaliteitsactie"])
        flow.append(Paragraph(f"- {r['Scenario']}: {route}", styles["JDENormal"]))

    def background(canvas, doc):
        canvas.setFillColor(colors.HexColor(PAGE_BEIGE))
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1)

    doc.build(flow, onFirstPage=background)
    pdf.seek(0)

    st.download_button(
        "📄 Download PDF (Compact)",
        data=pdf.getvalue(),
        file_name="winkans_advies.pdf",
        mime="application/pdf"
    )
