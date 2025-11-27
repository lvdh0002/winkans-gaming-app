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
# Session state: prijs/kwaliteit sync
# -------------------------
if "prijs_pct" not in st.session_state:
    st.session_state.prijs_pct = 40
if "kwaliteit_pct" not in st.session_state:
    st.session_state.kwaliteit_pct = 60

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


# -------------------------
# PART 3: SIDEBAR INPUTS
# -------------------------
st.sidebar.header("Instellingen")

# Aantal kwaliteitscriteria
num_criteria = st.sidebar.number_input(
    "Aantal kwaliteitscriteria",
    min_value=1, max_value=5,
    value=len(st.session_state.criteria),
    step=1,
    key="num_crit"
)

# Criteria lijst dynamisch bijwerken
criteria = st.session_state.criteria[:num_criteria] + \
           [f"Criteria {i+1}" for i in range(len(st.session_state.criteria), num_criteria)]
st.session_state.criteria = criteria

# Wegingen
st.sidebar.subheader("Wegingen (%)")
price_weight = st.sidebar.number_input(
    "Weging prijs (%)",
    min_value=0.0, max_value=100.0,
    value=st.session_state.price_weight,
    step=1.0,
    key="weight_price"
)
quality_weight = 100 - price_weight

# Beoordelingsschaal
st.sidebar.subheader("Beoordelingsschaal kwaliteit (bijv. 0,20,40,60,80,100)")
scale_input = st.sidebar.text_input(
    "Schaal",
    value=",".join(str(s) for s in st.session_state.score_scale),
    key="scale_in"
)
score_scale = [float(x.strip()) for x in scale_input.split(",")]
st.session_state.score_scale = score_scale

# Aantal concurrenten
num_competitors = st.sidebar.number_input(
    "Aantal concurrenten",
    min_value=1, max_value=10,
    value=st.session_state.num_competitors,
    key="num_comp"
)
st.session_state.num_competitors = num_competitors


# -------------------------
# PART 4: SCENARIO INPUTS
# -------------------------
st.sidebar.header("Scenario-invoer")

scenarios = []
for i in range(num_competitors):
    st.sidebar.subheader(f"Concurrent {i+1}")

    # Checkbox "Is goedkoopste"
    is_cheapest = st.sidebar.checkbox(
        "Is goedkoopste aanbieder?",
        value=False,
        key=f"cheap_{i}"
    )

    # Prijsmarge-input (alleen als niet goedkoopste)
    if is_cheapest:
        margin_pct = 0.0
    else:
        margin_pct = st.sidebar.number_input(
            "% duurder dan goedkoopste",
            min_value=0.0, max_value=200.0,
            value=10.0,
            step=0.1,
            key=f"margin_{i}"
        )

    # Kwaliteitsscores
    comp_scores = []
    for c in range(num_criteria):
        sc = st.sidebar.selectbox(
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

# Eigen aanbod
st.sidebar.header("Eigen aanbod")
self_margin = st.sidebar.number_input(
    "% duurder dan goedkoopste (jij)",
    min_value=0.0, max_value=200.0,
    value=10.0,
    step=0.1,
    key="self_margin"
)

self_scores = []
for c in range(num_criteria):
    sc = st.sidebar.selectbox(
        f"Jouw score op {criteria[c]}",
        options=score_scale,
        index=0,
        key=f"self_score_{c}"
    )
    self_scores.append(sc)



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

def absolute_price_points(margin, max_price_points):
    return float(max_price_points)*(1.0-float(margin)/100.0)


# -------------------------
# PART 6: CALCULATION & RESULTS
# -------------------------
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # Voorbeeld maxpunten en wegingen (kun je dynamisch maken)
    criterion_maxpoints = {c: 100 for c in criteria}
    criterion_weights = {c: 1 for c in criteria}

    jde_total, jde_breakdown = compute_quality_points(
        {c:self_scores[i] for i,c in enumerate(criteria)},
        criterion_maxpoints,
        criterion_weights,
        prijs_pct=quality_weight,
        criteria=criteria
    )
    max_price_points = int(round(price_weight))
    jde_p = int(round(absolute_price_points(self_margin, max_price_points)))
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
        comp_p = absolute_price_points(s["margin_pct"], max_price_points)
        comp_total += comp_p
        status = "WIN" if jde_total>comp_total else "LOSE" if jde_total<comp_total else "DRAW"

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
