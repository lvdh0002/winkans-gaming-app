import streamlit as st
import pandas as pd
import math
import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# -------------------------
# Session state defaults
# -------------------------
if "prijs_pct" not in st.session_state:
    st.session_state.prijs_pct = 40
if "kwaliteit_pct" not in st.session_state:
    st.session_state.kwaliteit_pct = 60
if "criteria" not in st.session_state:
    st.session_state.criteria = ["Flexibiliteit", "Dienstverlening", "Duurzaamheid"]
if "score_scale" not in st.session_state:
    st.session_state.score_scale = [0, 20, 40, 60, 80, 100]
if "num_competitors" not in st.session_state:
    st.session_state.num_competitors = 3
if "price_weight" not in st.session_state:
    st.session_state.price_weight = 40
if "margin_pct" not in st.session_state:
    st.session_state.margin_pct = 10.0

def update_prijs():
    st.session_state.kwaliteit_pct = 100 - st.session_state.prijs_pct

def update_kwaliteit():
    st.session_state.prijs_pct = 100 - st.session_state.kwaliteit_pct

# -------------------------
# PART 2: PAGE STYLE AND HEADER
# -------------------------
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');
h1,h2,h3,h4 { font-family: 'Oswald', sans-serif !important; font-weight:700; color:#7A1F1F; }
html,body,.stApp { background-color:#F3E9DB; font-family:'Segoe UI',sans-serif!important; color:#000; }
.stButton>button { font-family:'Oswald',sans-serif!important; font-weight:700; background:#7A1F1F; color:#fff; border-radius:6px; }
.stButton>button:hover { background:#4B2E2B; }
[data-testid="stSidebar"] > div:first-child { background:#A13D3B!important; color:#fff; }
[data-testid="stSidebar"] label { color:#fff!important; }
</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"
ACCENT_GOLD = "#C8A165"
PAGE_BEIGE = "#F3E9DB"
LOGO_PATH = os.path.join("assets","logo_jde.png")  # controleer pad

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# 2. Beoordelingsschaal (dropdown + custom)
st.sidebar.subheader("Beoordelingsschaal kwaliteit")
scale_options = {
    "0-20-40-60-80-100": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "0-10-20-30-40-50-60-70-80-90-100": list(range(0,101,10)),
    "Custom": "Custom"
}
selected_scale = st.sidebar.selectbox("Kies schaal", options=list(scale_options.keys()), index=0)

if selected_scale != "Custom":
    score_scale = scale_options[selected_scale]
else:
    custom_input = st.sidebar.text_input(
        "Custom schaal (komma gescheiden)",
        value=",".join(str(s) for s in st.session_state.score_scale)
    )
    # Zet custom input om naar floats, negeer lege waarden of niet-numerieke input
    score_scale = []
    for x in custom_input.split(","):
        try:
            score_scale.append(float(x.strip()))
        except ValueError:
            pass  # negeer niet-numerieke waarden

st.session_state.score_scale = score_scale

# -------------------------
# PART 4: CONCURRENTENSCORES IN HOOFDSCHERM
# -------------------------
st.header("Concurrentiescenario's")

num_competitors = st.number_input(
    "Aantal concurrenten",
    min_value=1, max_value=10,
    value=int(st.session_state.num_competitors),
    step=1
)
st.session_state.num_competitors = num_competitors

scenarios = []
for i in range(num_competitors):
    st.subheader(f"Concurrent {i+1}")
    is_cheapest = st.checkbox(f"Is goedkoopste aanbieder?", key=f"cheap_{i}")
    
    if is_cheapest:
        margin_pct = 0.0
    else:
        margin_pct = st.number_input(
            "% duurder dan goedkoopste",
            min_value=0.0, max_value=200.0,
            value=10.0,
            step=0.1,
            key=f"margin_{i}"
        )

    comp_scores = []
    for c in range(num_criteria):
        sc = st.selectbox(
            f"Score op {criteria[c]}",
            options=score_scale,
            index=0,
            key=f"comp_{i}_{c}"
        )
        comp_scores.append(sc)

    scenarios.append({
        "is_cheapest": is_cheapest,
        "margin_pct": margin_pct,
        "quality_scores": comp_scores
    })

# -------------------------
# PART 5: HELPER FUNCTIONS
# -------------------------
def score_to_raw_points(score, max_points):
    try:
        return (float(score)/100.0)*float(max_points)
    except:
        return 0.0

def compute_quality_points(scores, criterion_maxpoints, criterion_weights, prijs_pct, criteria):
    breakdown = {}
    total = 0.0
    sum_weights = sum(criterion_weights.values()) if criterion_weights else len(criteria)
    for c in criteria:
        maxp = criterion_maxpoints.get(c, 100)
        raw = score_to_raw_points(scores[c], maxp)
        norm = (raw/maxp) if maxp>0 else 0.0
        weight_frac = (criterion_weights.get(c,0)/sum_weights) if sum_weights>0 else (1.0/len(criteria))
        contrib = weight_frac * prijs_pct * norm
        breakdown[c] = {"raw_points": raw, "normalized": norm, "weight_frac": weight_frac, "contribution": contrib}
        total += contrib
    return total, breakdown

def absolute_price_points_1pct(margin, max_price_points):
    return float(max_price_points)*(1.0 - (margin/100.0 + 0.01))

# PDF exportfunctie
def generate_pdf(df, self_scores, scenarios, criteria, filename="winkans.pdf"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30,leftMargin=30, topMargin=30,bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='Title', fontSize=18, leading=22, alignment=1, textColor=PRIMARY_COLOR, fontName='Helvetica-Bold')
    header_style = ParagraphStyle(name='Header', fontSize=14, leading=18, textColor=PRIMARY_COLOR, fontName='Helvetica-Bold')
    normal_style = styles["Normal"]

    elements.append(Paragraph("Winkans Berekening", title_style))
    elements.append(Spacer(1,12))

    # Eigen scores
    elements.append(Paragraph("Eigen scores", header_style))
    data = [["Criteria", "Score"]]
    for i,c in enumerate(criteria):
        data.append([c, self_scores[i]])
    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(1,0),PRIMARY_COLOR),
                           ('TEXTCOLOR',(0,0),(1,0),colors.white),
                           ('ALIGN',(0,0),(-1,-1),'CENTER'),
                           ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                           ('GRID',(0,0),(-1,-1),0.5,colors.black)]))
    elements.append(t)
    elements.append(Spacer(1,12))

    # Concurrenten
    elements.append(Paragraph("Concurrentiescenario's", header_style))
    for idx, s in enumerate(scenarios, start=1):
        elements.append(Paragraph(f"Concurrent {idx}", normal_style))
        data = [["Criteria", "Score", "% duurder dan goedkoopste" if not s["is_cheapest"] else "Goedkoopste"]]
        for i,c in enumerate(criteria):
            data.append([c, s["quality_scores"][i], 0 if s["is_cheapest"] else s["margin_pct"]])
        t = Table(data, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(2,0),PRIMARY_COLOR),
                               ('TEXTCOLOR',(0,0),(2,0),colors.white),
                               ('ALIGN',(0,0),(-1,-1),'CENTER'),
                               ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                               ('GRID',(0,0),(-1,-1),0.5,colors.black)]))
        elements.append(t)
        elements.append(Spacer(1,12))

    # Resultaten
    elements.append(Paragraph("Resultaten overzicht", header_style))
    data = [df.columns.tolist()] + df.values.tolist()
    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PRIMARY_COLOR),
                           ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                           ('ALIGN',(0,0),(-1,-1),'CENTER'),
                           ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                           ('GRID',(0,0),(-1,-1),0.5,colors.black)]))
    elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# -------------------------
# PART 6: CALCULATIE & RESULTATEN
# -------------------------
st.header("Resultaten")

if st.button("Bereken winkansen"):
    criterion_maxpoints = {c: 100 for c in criteria}
    criterion_weights = {c: 1 for c in criteria}

    jde_total, jde_breakdown = compute_quality_points(
        {c:self_scores[i] for i,c in enumerate(criteria)},
        criterion_maxpoints,
        criterion_weights,
        prijs_pct=quality_weight,
        criteria=criteria
    )
    max_price_points = float(price_weight)
    jde_p = absolute_price_points_1pct(self_margin, max_price_points)
    jde_total += jde_p

    rows = []
    for idx, s in enumerate(scenarios, start=1):
        comp_scores_dict = {c:s["quality_scores"][i] for i,c in enumerate(criteria)}
        comp_total, comp_breakdown = compute_quality_points(
            comp_scores_dict,
            criterion_maxpoints,
            criterion_weights,
            prijs_pct=quality_weight,
            criteria=criteria
        )
        comp_p = absolute_price_points_1pct(s["margin_pct"], max_price_points)
        comp_total += comp_p

        status = "WIN" if jde_total > comp_total else "LOSE" if jde_total < comp_total else "DRAW"

        row = {
            "Scenario": f"{idx}",
            "Status": status,
            "JDE totaal": round(jde_total,2),
            "JDE prijs pts": int(round(jde_p)),
            "Conc totaal": round(comp_total,2),
            "Conc prijs pts": int(round(comp_p))
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    st.subheader("Resultaten overzicht")
    st.dataframe(df, use_container_width=True)

    # PDF download
    pdf_buffer = generate_pdf(df, self_scores, scenarios, criteria)
    st.download_button(
        label="Download PDF",
        data=pdf_buffer,
        file_name="winkans.pdf",
        mime="application/pdf"
    )
