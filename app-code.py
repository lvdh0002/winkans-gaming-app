### PART 1: IMPORTS AND SESSION STATE

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


### PART 2: PAGE STYLE AND HEADER

# -------------------------
# Page style / header
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
LOGO_PATH = os.path.join("assets","logo_jde.png")  # controleer dit pad

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)


### SIDEBAR INPUTS

# -------------------------
# Sidebar inputs
# -------------------------
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
st.sidebar.number_input("Prijs (%)", min_value=0, max_value=100, key="prijs_pct", on_change=update_prijs)
st.sidebar.number_input("Kwaliteit (%)", min_value=0, max_value=100, key="kwaliteit_pct", on_change=update_kwaliteit)

prijs_pct = st.session_state.prijs_pct
kwaliteit_pct = st.session_state.kwaliteit_pct
st.sidebar.markdown(f"**Opmerking:** prijs + kwaliteit = **{prijs_pct + kwaliteit_pct}** (altijd 100)")

# Score schaal
scales = {"0-2-4-6-8-10":[0,2,4,6,8,10],
          "0-20-40-60-80-100":[0,20,40,60,80,100],
          "0-25-50-75-100":[0,25,50,75,100],
          "Custom...":None}
scale_label = st.sidebar.selectbox("Score schaal", list(scales.keys()))
if scale_label != "Custom...":
    scale_values = scales[scale_label]
else:
    raw = st.sidebar.text_input("Eigen schaal (comma separated)", "0,25,50,75,100")
    try:
        scale_values = [float(x.strip()) for x in raw.split(",") if x.strip() != ""]
        if len(scale_values)<2: scale_values=[0,25,50,75,100]
    except:
        scale_values=[0,25,50,75,100]
max_scale = max(scale_values)

# Criteria names
criteria_input = st.sidebar.text_input("Criterianamen (komma-gescheiden)", "Duurzaamheid,Service")
criteria = [c.strip() for c in criteria_input.split(",") if c.strip()]
if not criteria:
    st.sidebar.error("Voeg minstens één criterium toe.")

# Per criterium: weighting & max points
criterion_weights = {}
criterion_maxpoints = {}
st.sidebar.markdown("### Per criterium: weging (%) & max punten")
for c in criteria:
    st.sidebar.markdown(f"**{c}**")
    w = st.sidebar.number_input(f"Weging {c} (%)", min_value=0.0, max_value=100.0, value=round(100.0/len(criteria),1), step=0.5, key=f"w_{c}")
    p = st.sidebar.number_input(f"Max punten {c}", min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key=f"p_{c}")
    criterion_weights[c] = float(w)
    criterion_maxpoints[c] = float(p)
sum_weights = sum(criterion_weights.values()) or 100.0

# JDE expected scores per criterion
verwachte_scores_eigen = {}
for c in criteria:
    sel = st.sidebar.selectbox(f"Score JDE voor {c}", [str(x) for x in scale_values], key=f"jde_score_{c}")
    try: verwachte_scores_eigen[c]=float(sel)
    except: verwachte_scores_eigen[c]=float(scale_values[0])
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (JDE)", min_value=0.0, max_value=100.0, value=10.0, step=0.1)


### PART 4: SCENARIO INPUTS

# -------------------------
# Scenarios input
# -------------------------
st.header("Concurrentsituaties")
num_scen = st.number_input("Aantal situaties", min_value=1, max_value=15, value=3, step=1)

scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}", expanded=False):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"name_{i}")
        is_cheapest = st.checkbox("Concurrent is goedkoopste?", key=f"cheap_{i}")
        marge = 0.0 if is_cheapest else st.number_input("% duurder dan goedkoopste (conc.)", min_value=0.0, max_value=100.0, value=margin_pct, step=0.1, key=f"marge_{i}")
        kval_scores = {}
        for c in criteria:
            sel = st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")
            try: kval_scores[c] = float(sel)
            except: kval_scores[c] = float(scale_values[0])
        scenarios.append({"naam": naam or f"Concurrent {i+1}", "marge": float(marge), "kval_scores": kval_scores})


### PART 5: HELPER FUNCTIONS
# -------------------------
# Helper functions & core math
# -------------------------
def score_to_raw_points(score, max_points_for_criterion):
    try: return (float(score)/float(max_scale))*float(max_points_for_criterion)
    except: return 0.0

def compute_quality_points_and_breakdown(scores: dict):
    breakdown = {}
    total = 0.0
    for c in criteria:
        maxp = criterion_maxpoints.get(c,0.0)
        raw = score_to_raw_points(scores.get(c,0.0), maxp)
        norm = (raw/maxp) if maxp>0 else 0.0
        weight_frac = (criterion_weights.get(c,0.0)/sum_weights) if sum_weights>0 else (1.0/len(criteria))
        contribution = weight_frac * kwaliteit_pct * norm
        breakdown[c] = {"raw_points":round(raw,2), "normalized":round(norm,4), "weight_frac":round(weight_frac,4), "contribution":round(contribution,4)}
        total += contribution
    return total, breakdown

def absolute_price_points(marge, M):
    return float(M)*(1.0-float(marge)/100.0)

def required_drop_piecewise(my_margin, comp_margin, Qm, Qc, M):
    try:
        m_req_A = comp_margin + (100.0/M)*(Qm-Qc)
        m_req_B = comp_margin - (100.0/M)*(Qc-Qm)
        m_req = m_req_A if m_req_A>=comp_margin else m_req_B
        drop = max(0.0, my_margin - m_req)
        drop_int = int(math.ceil(drop))
        target_int = int(round(my_margin - drop_int))
        return drop_int, target_int
    except Exception:
        return 0, int(round(my_margin))

def determine_status_and_actions(jde_total, jde_q, jde_p, comp_total, comp_q, comp_p, my_margin, comp_margin):
    eps=1e-9
    if jde_total>comp_total+eps: status="WIN"
    elif jde_total<comp_total-eps: status="LOSE"
    else: status="DRAW"

    drop_int,target_int = required_drop_piecewise(my_margin, comp_margin, jde_q, comp_q, max_price_points)
    if status!="WIN" and drop_int==0:
        drop_int=1
        target_int=int(round(my_margin-1))
    prijsactie="Geen actie nodig" if status=="WIN" else f"Verlaag {drop_int}% (naar {target_int}%)"

    qual_action="-"
    if status!="WIN":
        found=False
        for c in criteria:
            cur=float(verwachte_scores_eigen.get(c,0.0))
            higher=[x for x in scale_values if float(x)>cur]
            for nxt in higher:
                maxp=criterion_maxpoints.get(c,0.0)
                raw_cur=score_to_raw_points(cur,maxp)
                raw_nxt=score_to_raw_points(nxt,maxp)
                norm_cur=raw_cur/maxp if maxp>0 else 0.0
                norm_nxt=raw_nxt/maxp if maxp>0 else 0.0
                weight_frac=(criterion_weights.get(c,0.0)/sum_weights) if sum_weights>0 else (1.0/len(criteria))
                contrib_cur=weight_frac*kwaliteit_pct*norm_cur
                contrib_nxt=weight_frac*kwaliteit_pct*norm_nxt
                gain=contrib_nxt-contrib_cur
                if (jde_q+gain+jde_p)>(comp_total+1e-6):
                    qual_action=f"Verhoog {c} {int(round(cur))}→{int(round(nxt))} (+{round(gain,2)} ptn)"
                    found=True
                    break
            if found: break
        if not found: qual_action="Ontoereikend"

    return status, prijsactie, qual_action, drop_int

def advice_route_text(price_action, qual_action):
    p_needed=("Verlaag" in price_action) and ("Geen actie nodig" not in price_action)
    q_needed=(qual_action not in ["-","Ontoereikend",""]) and ("Verhoog" in qual_action)
    if p_needed and q_needed: return "Adviesroute: prijs + kwaliteit"
    if p_needed and not q_needed: return "Adviesroute: prijs"
    if not p_needed and q_needed: return "Adviesroute: kwaliteit"
    return "Adviesroute: geen actie"

import os
print(os.path.exists("assets/Oswald-Bold.ttf"))       # True?
print(os.path.exists("assets/Aptos-Regular.ttf"))    # True?
print(os.path.exists("assets/Aptos-Italic.ttf"))     # True?
