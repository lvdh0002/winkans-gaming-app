import streamlit as st
import pandas as pd
import math
import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)

# ===============================
# SESSION STATE + PRICE/QUALITY SYNC
# ===============================

if "prijs_pct" not in st.session_state:
    st.session_state.prijs_pct = 40
if "kwaliteit_pct" not in st.session_state:
    st.session_state.kwaliteit_pct = 60

def update_prijs():
    st.session_state.kwaliteit_pct = 100 - st.session_state.prijs_pct

def update_kwaliteit():
    st.session_state.prijs_pct = 100 - st.session_state.kwaliteit_pct


# ===============================
# PAGE STYLE (JDE look)
# ===============================

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
    font-family: 'Segoe UI', sans-serif !important;
    color: #000;
}

.stButton>button {
    font-family: 'Oswald', sans-serif !important;
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

# ===============================
# HEADER
# ===============================

if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=120)

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# ===============================
# SIDEBAR
# ===============================

st.sidebar.header("Stap 1: Beoordelingsmethodiek")

# 1. Prijs & kwaliteit met automatische synchronisatie
st.sidebar.number_input(
    "Prijs (%)",
    min_value=0, max_value=100,
    key="prijs_pct",
    on_change=update_prijs
)
st.sidebar.number_input(
    "Kwaliteit (%)",
    min_value=0, max_value=100,
    key="kwaliteit_pct",
    on_change=update_kwaliteit
)

prijs_pct = st.session_state.prijs_pct
kwaliteit_pct = st.session_state.kwaliteit_pct

# 2. Score schaalkeuze
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-20-40-60-80-100": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "Custom...": None
}

scale_label = st.sidebar.selectbox("Score schaal", list(scales.keys()))
if scale_label != "Custom...":
    scale_values = scales[scale_label]
else:
    raw = st.sidebar.text_input("Eigen schaal", "0,25,50,75,100")
    try:
        scale_values = [float(x.strip()) for x in raw.split(",")]
    except:
        scale_values = [0,25,50,75,100]

max_scale = max(scale_values)

# 3. Criteria
criteria = [c.strip() for c in st.sidebar.text_input("Criterianamen", "Duurzaamheid,Service").split(",") if c.strip()]

# Automatische verdeling max quality points
orig_points = {c: 1 for c in criteria}  # gelijke basisverdeling
sum_orig = sum(orig_points.values())

max_points_criteria = {
    c: round((orig_points[c] / sum_orig) * kwaliteit_pct, 2)
    for c in criteria
}

max_price_points = prijs_pct

# 4. JDE kwaliteitsscores
verwachte_scores_eigen = {}
for c in criteria:
    sel = st.sidebar.selectbox(f"Score JDE voor {c}", [str(x) for x in scale_values], key=f"jde_{c}")
    verwachte_scores_eigen[c] = float(sel)

# 5. JDE marge
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (JDE)", 0.0, 100.0, 10.0, 0.1)


# ===============================
# CONCURRENT SCENARIO'S
# ===============================

st.header("📥 Concurrentsituaties")

num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []

for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        cheap = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        marge = 0 if cheap else st.number_input("Marge (%)", 0.0, 100.0, margin_pct, 0.1, key=f"marge{i}")

        kval = {}
        for c in criteria:
            sel = st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"sc_{i}_{c}")
            kval[c] = float(sel)

        scenarios.append({"naam": naam, "marge": marge, "kval_scores": kval})


# ===============================
# HELPER FUNCTIONS
# ===============================

def score_to_points(score, max_points):
    return (score / max_scale) * max_points

def compute_quality_points(scores):
    return sum(score_to_points(scores[c], max_points_criteria[c]) for c in criteria)

def absolute_price_points(marge, maxp):
    return maxp * (1 - marge / 100)

def required_drop(my_m, comp_m, Qm, Qc, M):
    try:
        m_req_A = comp_m + (100 / M) * (Qm - Qc)
        m_req_B = comp_m - (100 / M) * (Qc - Qm)
        m_req = m_req_A if m_req_A >= comp_m else m_req_B

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


# ===============================
# BEREKENING
# ===============================

st.header("Resultaten")

if st.button("Bereken winkansen"):

    jde_q = compute_quality_points(verwachte_scores_eigen)
    jde_p = absolute_price_points(margin_pct, max_price_points)
    jde_total = jde_q + jde_p

    rows = []

    for s in scenarios:

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

        drop, target = required_drop(margin_pct, s["marge"], jde_q, comp_q, max_price_points)
        prijsactie = "Geen actie nodig" if status == "WIN" else f"Verlaag {drop}% → {target}%"

        qual_action = "-"
        if status != "WIN":
            for c in criteria:
                cur = verwachte_scores_eigen[c]
                higher = [x for x in scale_values if x > cur]

                for nxt in higher:
                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                    if jde_q + gain + jde_p > comp_total:
                        qual_action = f"Verhoog {c} {int(cur)} → {int(nxt)} (+{int(gain)}p)"
                        break
                if qual_action != "-":
                    break

            if qual_action == "-":
                qual_action = "Ontoereikend"

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
            "Kwaliteitsactie": qual_action
        })

    df = pd.DataFrame(rows)

    st.subheader("Volledige resultaten")
    st.dataframe(df, use_container_width=True)

    # ===============================
    # PDF EXPORT
    # ===============================

    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=landscape(A4),
                            leftMargin=30,rightMargin=30,topMargin=30,bottomMargin=30)

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="JDETitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor(PRIMARY_COLOR),
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        name="JDENormal",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.black
    ))

    styles.add(ParagraphStyle(
        name="JDEItalic",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#444")
    ))

    flow = []

    if os.path.exists(LOGO_PATH):
        flow.append(Image(LOGO_PATH, width=100, height=40))
        flow.append(Spacer(1, 8))

    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["JDETitle"]))
    flow.append(Spacer(1, 10))

    jde_scores = ", ".join(f"{c}: {int(verwachte_scores_eigen[c])}" for c in criteria)
    flow.append(Paragraph(f"<b>JDE:</b> {margin_pct}% duurder, scores: {jde_scores}", styles["JDENormal"]))
    flow.append(Spacer(1, 10))

    pdf_cols = ["Scenario","Status","Verschil","Prijsactie","Kwaliteitsactie"]
    table_data = [pdf_cols] + [[r[c] for c in pdf_cols] for r in rows]

    table = Table(table_data, colWidths=[140,70,60,150,150])
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
    ]))

    flow.append(table)
    flow.append(Spacer(1, 14))

    flow.append(Paragraph("<b>Adviesroutes:</b>", styles["JDENormal"]))
    for r in rows:
        route = advice_route(r["Prijsactie"], r["Kwaliteitsactie"])
        flow.append(Paragraph(f"- {r['Scenario']}: {route}", styles["JDENormal"]))

    def bg(canvas, doc):
        canvas.setFillColor(colors.HexColor(PAGE_BEIGE))
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1)

    doc.build(flow, onFirstPage=bg)
    pdf_buf.seek(0)

    st.download_button("📄 Download PDF", data=pdf_buf.getvalue(), file_name="winkans_advies.pdf", mime="application/pdf")
