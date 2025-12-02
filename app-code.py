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
# SETUP & STIJL
# -------------------------
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');

/* Algemene fonts en kleuren */
h1,h2,h3,h4 { font-family: 'Oswald', sans-serif !important; font-weight:700; color:#7A1F1F; }
html,body,.stApp { background-color:#F3E9DB; font-family:'Segoe UI',sans-serif!important; color:#000; }
.stButton>button { font-family:'Oswald', sans-serif!important; font-weight:700; background:#7A1F1F; color:#fff; border-radius:6px; }

/* ---------------------------------------------------- */
/* CORRECTIE: Sidebar Kleuren vastzetten op #7A1F1F     */
/* ---------------------------------------------------- */
[data-testid="stSidebar"] > div:first-child { 
    background:#7A1F1F!important; /* Hoofdmerk kleur */
    color:#fff; 
}
[data-testid="stSidebar"] label { 
    color:#fff!important; 
}


/* TRUC: Maak van het main-screen tekstveld een Header */
.stApp > header + div [data-testid="stTextInput"] input {
    font-family: 'Oswald', sans-serif !important;
    font-weight: 700 !important;
    font-size: 26px !important;
    color: #7A1F1F !important;
    background-color: transparent !important;
    border: none !important;
    border-bottom: 2px solid #7A1F1F !important;
    padding-left: 0px !important;
    padding-bottom: 5px !important;
    height: auto !important;
    box-shadow: none !important;
}

.stApp > header + div [data-testid="stTextInput"] input:focus {
    box-shadow: none !important;
    outline: none !important;
    border-bottom: 3px solid #7A1F1F !important;
}

/* Sidebar inputs normaal houden (resetten) */
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    font-family: 'Segoe UI', sans-serif !important;
    font-size: 14px !important;
    font-weight: 400 !important;
    color: black !important;
    border: 1px solid #ccc !important;
    background-color: white !important;
}

</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"
LOGO_PATH = os.path.join("assets", "logo_jde.png")

# Fonts registreren voor PDF (aanname dat dit in de setup staat)
try:
    # Let op: Deze paden moeten kloppen met je lokale bestandslocatie.
    pdfmetrics.registerFont(TTFont("OswaldBold", os.path.join("assets", "Oswald-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Aptos", os.path.join("assets", "Aptos-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", os.path.join("assets", "Aptos-Italic.ttf")))
except:
    # Fallback indien bestanden niet gevonden
    pdfmetrics.registerFont(TTFont("OswaldBold", "Helvetica-Bold")) 
    pdfmetrics.registerFont(TTFont("Aptos", "Helvetica"))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", "Helvetica-Oblique"))

# -------------------------
# SESSION STATE & CALLBACKS
# -------------------------
if "prijs_pct" not in st.session_state: st.session_state.prijs_pct = 40
if "kwaliteit_pct" not in st.session_state: st.session_state.kwaliteit_pct = 60
if "criteria" not in st.session_state: st.session_state.criteria = ["Flexibiliteit", "Dienstverlening", "Duurzaamheid"]
if "score_scale" not in st.session_state: st.session_state.score_scale = [0, 20, 40, 60, 80, 100]
if "num_competitors" not in st.session_state: st.session_state.num_competitors = 3
if "criteria_data" not in st.session_state: st.session_state.criteria_data = []

def update_prijs(): st.session_state.kwaliteit_pct = 100 - st.session_state.prijs_pct
def update_kwaliteit(): st.session_state.prijs_pct = 100 - st.session_state.kwaliteit_pct
def sync_weight_max(i):
    if f"crit_weight_{i}" in st.session_state:
        st.session_state[f"crit_max_{i}"] = st.session_state[f"crit_weight_{i}"]

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.header("Beoordelingsmethodiek")

col_p, col_q = st.sidebar.columns(2)
prijs_pct = col_p.number_input("Weging prijs (%)", 0, 100, int(st.session_state.prijs_pct), 1, key="prijs_pct", on_change=update_prijs)
kwaliteit_pct = col_q.number_input("Weging kwaliteit (%)", 0, 100, int(st.session_state.kwaliteit_pct), 1, key="kwaliteit_pct", on_change=update_kwaliteit)

st.sidebar.subheader("Beoordelingsschaal")
scale_options = {"0-20-40-60-80-100": [0,20,40,60,80,100], "0-25-50-75-100": [0,25,50,75,100], "Custom": None}
sel_scale = st.sidebar.selectbox("Kies schaal", list(scale_options.keys()), 0)
score_scale = scale_options[sel_scale] if sel_scale != "Custom" else [float(x) for x in st.sidebar.text_input("Custom (komma)", "0,10,100").split(",") if x.strip()]
st.session_state.score_scale = score_scale

st.sidebar.subheader("Criteria Details")
num_crit = st.sidebar.number_input("Aantal criteria", 1, 10, len(st.session_state.criteria))
if len(st.session_state.criteria) < num_crit: st.session_state.criteria += [f"Crit {i+1}" for i in range(len(st.session_state.criteria), num_crit)]
else: st.session_state.criteria = st.session_state.criteria[:num_crit]

criteria_data = []
def_w = int(kwaliteit_pct/num_crit) if num_crit>0 else 0
for i in range(num_crit):
    st.sidebar.markdown(f"**Criterium {i+1}**")
    nm = st.sidebar.text_input("Naam", st.session_state.criteria[i], key=f"crit_name_{i}")
    c1, c2 = st.sidebar.columns(2)
    w = c1.number_input("Weging", 0, 100, def_w, key=f"crit_weight_{i}", on_change=sync_weight_max, args=(i,))
    if f"crit_max_{i}" not in st.session_state: st.session_state[f"crit_max_{i}"] = w
    mp = c2.number_input("Max pts", 1, 200, key=f"crit_max_{i}")
    criteria_data.append({"name": nm, "weight": w, "max_points": mp})
st.session_state.criteria_data = criteria_data

st.sidebar.markdown("---")
max_price_points = st.sidebar.number_input("Max punten prijs", 1, 100, int(prijs_pct))
st.sidebar.header("Jouw Aanbod (JDE)")
self_margin = st.sidebar.number_input("Jouw prijs (% boven laagste)", 0.0, 200.0, 10.0, 0.1)
self_scores = {cd['name']: st.sidebar.selectbox(f"Jouw score: {cd['name']}", score_scale, index=len(score_scale)-1) for cd in criteria_data}

# -------------------------
# HOOFDSCHERM: CONCURRENTEN (GRID LAYOUT)
# -------------------------
st.header("Concurrentiescenario's")
num_competitors = st.number_input("Aantal concurrenten", 1, 12, st.session_state.num_competitors)
st.session_state.num_competitors = num_competitors

scenarios = []
cols_per_row = 4

for i in range(0, num_competitors, cols_per_row):
    cols = st.columns(min(cols_per_row, num_competitors - i))
    
    for j, col in enumerate(cols):
        idx = i + j
        with col:
            # ----------------------------------------------------
            # HIER IS HET AANGEPASTE VELD
            # label_visibility="collapsed" verbergt het kleine label
            # de CSS bovenaan maakt de tekst groot en dikgedrukt
            # ----------------------------------------------------
            c_name = st.text_input(
                f"Naam Concurrent {idx+1}", # Label nodig voor interne werking
                value=f"Concurrent {idx+1}", 
                key=f"c_name_{idx}",
                label_visibility="collapsed" 
            )
            
            is_cheap = st.checkbox("Is goedkoopste?", key=f"c_cheap_{idx}")
            if is_cheap:
                c_margin = 0.0
                st.caption("Marge: 0% (basis)")
            else:
                c_margin = st.number_input(f"% Duurder", 0.0, 200.0, 5.0, 0.1, key=f"c_marg_{idx}")
            
            c_scores = {}
            for cd in criteria_data:
                c_scores[cd['name']] = st.selectbox(f"{cd['name']}", score_scale, index=0, key=f"c_sc_{idx}_{cd['name']}")
            
            scenarios.append({
                "naam": c_name,
                "marge": c_margin,
                "kval_scores": c_scores
            })
    
    st.markdown("<br>", unsafe_allow_html=True)

# -------------------------
# REKENLOGICA & ADVIES
# -------------------------
def absolute_price_points(margin_pct, max_points):
    pts = float(max_points) * (1.0 - (margin_pct/100.0))
    return max(0.0, pts)

def compute_quality_points(scores_dict):
    breakdown = {}
    total = 0.0
    for crit in st.session_state.criteria_data:
        raw = (float(scores_dict.get(crit['name'], 0)) / 100.0) * crit['max_points']
        breakdown[crit['name']] = raw
        total += raw
    return total, breakdown

def calculate_precise_advice(jde_total, jde_qual, jde_current_margin, comp_total, max_price_pts):
    diff = jde_total - comp_total
    
    if diff > 0:
        return "WIN", "Behoud prijsstrategie", int(diff)

    # We willen winnen (bijv +0.1 pt), niet gelijkspelen
    target_points_needed = comp_total + 0.1
    required_price_points = target_points_needed - jde_qual
    
    if required_price_points > max_price_pts:
        return "VERLIES", "Kwaliteitsgat te groot; niet te dichten met alleen prijs.", int(diff)
    
    # Marge berekening: Pts = Max * (1 - Marge/100)
    # Dus Marge = 100 * (1 - Pts/Max)
    required_margin_pct = 100.0 * (1.0 - (required_price_points / max_price_pts))
    
    # Veiligheidsmarge: zorg dat we net iets scherper zijn (-1%)
    safe_margin = required_margin_pct - 1.0 
    
    current_index = 100.0 + jde_current_margin
    new_index = 100.0 + safe_margin
    price_drop_pct = ((current_index - new_index) / current_index) * 100.0
    
    if safe_margin < 0:
        return "VERLIES", f"Onrealistisch: je moet {abs(safe_margin):.1f}% onder de laagste marktprijs.", int(diff)
        
    return "VERLIES", f"Verlaag prijs met {price_drop_pct:.1f}% (nieuwe marge: {safe_margin:.1f}%)", int(diff)

import streamlit as st
import pandas as pd
import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# -------------------------
# SETUP & STIJL
# -------------------------
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');

/* Algemene fonts en kleuren */
h1,h2,h3,h4 { font-family: 'Oswald', sans-serif !important; font-weight:700; color:#7A1F1F; }
html,body,.stApp { background-color:#F3E9DB; font-family:'Segoe UI',sans-serif!important; color:#000; }
.stButton>button { font-family:'Oswald', sans-serif!important; font-weight:700; background:#7A1F1F; color:#fff; border-radius:6px; }

/* Sidebar Kleuren vastzetten */
[data-testid="stSidebar"] > div:first-child { 
    background:#7A1F1F!important; 
    color:#fff; 
}
[data-testid="stSidebar"] label { 
    color:#fff!important; 
}


/* TRUC: Maak van het main-screen tekstveld een Header (Concurrent Naam) */
.stApp > header + div [data-testid="stTextInput"] input {
    font-family: 'Oswald', sans-serif !important;
    font-weight: 700 !important;
    font-size: 26px !important;
    color: #7A1F1F !important;
    background-color: transparent !important;
    border: none !important;
    border-bottom: 2px solid #7A1F1F !important;
    padding-left: 0px !important;
    padding-bottom: 5px !important;
    height: auto !important;
    box-shadow: none !important;
}

.stApp > header + div [data-testid="stTextInput"] input:focus {
    box-shadow: none !important;
    outline: none !important;
    border-bottom: 3px solid #7A1F1F !important;
}

/* Sidebar inputs normaal houden (resetten) */
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    font-family: 'Segoe UI', sans-serif !important;
    font-size: 14px !important;
    font-weight: 400 !important;
    color: black !important;
    border: 1px solid #ccc !important;
    background-color: white !important;
}

</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"
LOGO_PATH = os.path.join("assets", "logo_jde.png") 

# Fonts registreren voor PDF (aanname dat dit in de setup staat)
try:
    pdfmetrics.registerFont(TTFont("OswaldBold", os.path.join("assets", "Oswald-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Aptos", os.path.join("assets", "Aptos-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", os.path.join("assets", "Aptos-Italic.ttf")))
except:
    pdfmetrics.registerFont(TTFont("OswaldBold", "Helvetica-Bold")) 
    pdfmetrics.registerFont(TTFont("Aptos", "Helvetica"))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", "Helvetica-Oblique"))

# -------------------------
# SESSION STATE & CALLBACKS
# -------------------------
if "prijs_pct" not in st.session_state: st.session_state.prijs_pct = 40
if "kwaliteit_pct" not in st.session_state: st.session_state.kwaliteit_pct = 60
if "criteria" not in st.session_state: st.session_state.criteria = ["Duurzaamheid", "Service"]
if "score_scale" not in st.session_state: st.session_state.score_scale = [0, 20, 40, 60, 80, 100]
if "num_competitors" not in st.session_state: st.session_state.num_competitors = 3
if "criteria_data" not in st.session_state: st.session_state.criteria_data = []

# Callback functies voor synchronisatie
def update_prijs(): st.session_state.kwaliteit_pct = 100 - st.session_state.prijs_pct
def update_kwaliteit(): st.session_state.prijs_pct = 100 - st.session_state.kwaliteit_pct
def sync_weight_max(i):
    if f"crit_weight_{i}" in st.session_state:
        st.session_state[f"crit_max_{i}"] = st.session_state[f"crit_weight_{i}"]
def sync_num_competitors():
    st.session_state.num_competitors = st.session_state.num_competitors_input

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.header("Beoordelingsmethodiek")

col_p, col_q = st.sidebar.columns(2)
prijs_pct = col_p.number_input("Weging prijs (%)", 0, 100, int(st.session_state.prijs_pct), 1, key="prijs_pct", on_change=update_prijs)
kwaliteit_pct = col_q.number_input("Weging kwaliteit (%)", 0, 100, int(st.session_state.kwaliteit_pct), 1, key="kwaliteit_pct", on_change=update_kwaliteit)

st.sidebar.subheader("Beoordelingsschaal")
scale_options = {"0-20-40-60-80-100": [0,20,40,60,80,100], "0-25-50-75-100": [0,25,50,75,100], "Custom": None}
sel_scale = st.sidebar.selectbox("Kies schaal", list(scale_options.keys()), 0)
score_scale = scale_options[sel_scale] if sel_scale != "Custom" else [float(x) for x in st.sidebar.text_input("Custom (komma)", "0,10,100").split(",") if x.strip()]
st.session_state.score_scale = score_scale

st.sidebar.subheader("Criteria Details")
num_crit = st.sidebar.number_input("Aantal criteria", 1, 10, len(st.session_state.criteria))
if len(st.session_state.criteria) < num_crit: st.session_state.criteria += [f"Crit {i+1}" for i in range(len(st.session_state.criteria), num_crit)]
else: st.session_state.criteria = st.session_state.criteria[:num_crit]

criteria_data = []
def_w = int(kwaliteit_pct/num_crit) if num_crit>0 else 0
for i in range(num_crit):
    st.sidebar.markdown(f"**Criterium {i+1}**")
    nm = st.sidebar.text_input("Naam", st.session_state.criteria[i], key=f"crit_name_{i}")
    c1, c2 = st.sidebar.columns(2)
    w = c1.number_input("Weging", 0, 100, def_w, key=f"crit_weight_{i}", on_change=sync_weight_max, args=(i,))
    if f"crit_max_{i}" not in st.session_state: st.session_state[f"crit_max_{i}"] = w
    mp = c2.number_input("Max pts", 1, 200, key=f"crit_max_{i}")
    criteria_data.append({"name": nm, "weight": w, "max_points": mp})
st.session_state.criteria_data = criteria_data

st.sidebar.markdown("---")
max_price_points = st.sidebar.number_input("Max punten prijs", 1, 100, int(prijs_pct))
st.sidebar.header("Jouw Aanbod (JDE)")
self_margin = st.sidebar.number_input("Jouw prijs (% boven laagste)", 0.0, 200.0, 10.0, 0.1)
self_scores = {cd['name']: st.sidebar.selectbox(f"Jouw score: {cd['name']}", score_scale, index=len(score_scale)-1) for cd in criteria_data}

# -------------------------
# HOOFDSCHERM: CONCURRENTEN (GRID LAYOUT)
# -------------------------
st.header("Concurrentiescenario's")
num_competitors = st.number_input(
    "Aantal concurrenten", 
    1, 
    12, 
    st.session_state.num_competitors,
    key="num_competitors_input", 
    on_change=sync_num_competitors 
)
st.session_state.num_competitors = num_competitors

scenarios = []
cols_per_row = 4

for i in range(0, num_competitors, cols_per_row):
    cols = st.columns(min(cols_per_row, num_competitors - i))
    
    for j, col in enumerate(cols):
        idx = i + j
        with col:
            c_name = st.text_input(
                f"Naam Concurrent {idx+1}", 
                value=f"Concurrent {idx+1}", 
                key=f"c_name_{idx}",
                label_visibility="collapsed" 
            )
            
            is_cheap = st.checkbox("Is goedkoopste?", key=f"c_cheap_{idx}")
            if is_cheap:
                c_margin = 0.0
                st.caption("Marge: 0% (basis)")
            else:
                c_margin = st.number_input(f"% Duurder", 0.0, 200.0, 5.0, 0.1, key=f"c_marg_{idx}")
            
            c_scores = {}
            for cd in criteria_data:
                c_scores[cd['name']] = st.selectbox(f"{cd['name']}", score_scale, index=0, key=f"c_sc_{idx}_{cd['name']}")
            
            scenarios.append({
                "naam": c_name,
                "marge": c_margin,
                "kval_scores": c_scores
            })
    
    st.markdown("<br>", unsafe_allow_html=True)

# -------------------------
# REKENLOGICA & ADVIES
# -------------------------
def absolute_price_points(margin_pct, max_points):
    """Berekent de punten op basis van de marge en maximale punten."""
    pts = float(max_points) * (1.0 - (margin_pct/100.0))
    return max(0.0, pts)

def compute_quality_points(scores_dict):
    """Berekent de totale en breakdown kwaliteitspunten."""
    breakdown = {}
    total = 0.0
    for crit in st.session_state.criteria_data:
        raw = (float(scores_dict.get(crit['name'], 0)) / 100.0) * crit['max_points']
        breakdown[crit['name']] = raw
        total += raw
    return total, breakdown

def calculate_precise_advice(jde_total, jde_qual, jde_current_margin, comp_total, max_price_pts):
    """Berekent hoeveel de prijs moet zakken om met 1% marge te winnen."""
    diff = jde_total - comp_total
    
    if diff > 0:
        return "WIN", "Geen actie nodig", round(diff, 1)

    target_points_needed = comp_total + 0.1
    required_price_points = target_points_needed - jde_qual
    
    if required_price_points > max_price_pts:
        return "VERLIES", "Kwaliteitsgat te groot; niet te dichten met alleen prijs.", round(diff, 1)
    
    required_margin_pct = 100.0 * (1.0 - (required_price_points / max_price_pts))
    
    safe_margin = required_margin_pct - 1.0 
    
    current_index = 100.0 + jde_current_margin
    new_index = 100.0 + safe_margin
    price_drop_pct = ((current_index - new_index) / current_index) * 100.0
    
    if safe_margin < 0:
        return "VERLIES", f"Verlaag {price_drop_pct:.1f}% (naar 0%); Onrealistisch", round(diff, 1) # Toon 0% marge in advies
        
    return "VERLIES", f"Verlaag {price_drop_pct:.1f}% (naar {safe_margin:.1f}%)", round(diff, 1)

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
import io, os

# Fonts registreren (toegevoegd: Aptos-Italic)
oswald_path = os.path.join("assets", "Oswald-Bold.ttf")
aptos_path = os.path.join("assets", "Aptos-Regular.ttf")
aptos_italic_path = os.path.join("assets", "Aptos-Italic.ttf")

try:
    pdfmetrics.registerFont(TTFont("OswaldBold", oswald_path))
    pdfmetrics.registerFont(TTFont("Aptos", aptos_path))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", aptos_italic_path)) # Toegevoegd
except Exception as e:
    st.warning(f"Kon PDF fonts niet laden: {e}. Gebruik fallback fonts.")
    pdfmetrics.registerFont(TTFont("OswaldBold", "Helvetica-Bold"))
    pdfmetrics.registerFont(TTFont("Aptos", "Helvetica"))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", "Helvetica-Oblique"))

st.header("Resultaten")

if st.button("Bereken winkansen"):
    # Berekeningen
    # Aanname: deze functies en variabelen zijn gedefinieerd in eerdere delen.
    # (compute_quality_points_and_breakdown, absolute_price_points, determine_status_and_actions, etc.)
    # (verwachte_scores_eigen, prijs_pct, margin_pct, scenarios, criteria, criterion_weights, criterion_maxpoints, scale_label, LOGO_PATH)

    jde_q_total,jde_breakdown=compute_quality_points_and_breakdown(verwachte_scores_eigen)
    max_price_points=float(prijs_pct)
    jde_p=absolute_price_points(margin_pct,max_price_points)
    jde_total=jde_q_total+jde_p

    rows=[]
    for idx,s in enumerate(scenarios,start=1):
        comp_q_total,comp_breakdown=compute_quality_points_and_breakdown(s["kval_scores"])
        comp_p=absolute_price_points(s["marge"],max_price_points)
        comp_total=comp_q_total+comp_p

        status, prijsactie, kwalactie, drop_int=determine_status_and_actions(
            jde_total,jde_q_total,jde_p,comp_total,comp_q_total,comp_p,
            margin_pct,s["marge"]
        )
        verschil=int(round(jde_total-comp_total))

        row={"Scenario":f"{idx}. {s['naam']}",
             "Status":status,
             "Verschil":verschil,
             "JDE totaal":round(jde_total,2),
             "JDE prijs pts":round(jde_p,2),
             "JDE kwaliteit pts (totaal)":round(jde_q_total,2),
             "Conc totaal":round(comp_total,2),
             "Conc prijs pts":round(comp_p,2),
             "Conc kwaliteit pts (totaal)":round(comp_q_total,2),
             "Prijsactie":prijsactie,
             "Kwaliteitsactie":kwalactie}

        for c in criteria:
            row[f"JDE {c} raw_pts"]=jde_breakdown[c]["raw_points"]
            row[f"JDE {c} contrib"]=jde_breakdown[c]["contribution"]
            row[f"Conc {c} raw_pts"]=comp_breakdown[c]["raw_points"]
            row[f"Conc {c} contrib"]=comp_breakdown[c]["contribution"]

        rows.append(row)

    df=pd.DataFrame(rows)
    st.subheader("Volledige resultaten (per criterium breakdown)")
    st.dataframe(df,use_container_width=True)

    csv_bytes=df.to_csv(index=False).encode("utf-8")
    st.download_button("Download volledige resultaten (CSV)", data=csv_bytes, file_name="winkans_volledig.csv", mime="text/csv")

    # -------------------------
    # Compact PDF
    # -------------------------
    pdf_buf=io.BytesIO()
    doc=SimpleDocTemplate(pdf_buf,pagesize=landscape(A4),
                          leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=24)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="JDETitle", fontName="OswaldBold", fontSize=20, leading=24, textColor=colors.HexColor("#333")))
    styles.add(ParagraphStyle(name="JDESub", fontName="OswaldBold", fontSize=12, leading=14, textColor=colors.HexColor("#333")))
    styles.add(ParagraphStyle(name="JDENormal", fontName="Aptos", fontSize=10, leading=13, textColor=colors.HexColor("#333")))
    styles.add(ParagraphStyle(name="JDEItalic", fontName="Aptos-Italic", fontSize=9, leading=11, textColor=colors.HexColor("#444"))) # Aangepast naar Aptos-Italic

    flow=[]

    # Header table met logo
    logo_width = 0 # Initialiseren voor het geval de LOGO_PATH niet bestaat
    if os.path.exists(LOGO_PATH):
        try:
            img_reader=ImageReader(LOGO_PATH)
            iw,ih=img_reader.getSize()
            logo_width=120
            logo_height=logo_width*(ih/iw)
            logo=Image(LOGO_PATH,width=logo_width,height=logo_height)
        except:
            logo=Paragraph("", styles["JDENormal"])
    else:
        logo=Paragraph("", styles["JDENormal"])

    header_table=Table([[logo, Paragraph("Advies: Winkans & Acties — BPKV", styles["JDETitle"])]], colWidths=[logo_width+8,500])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#FFFAF6")),
        ('VALIGN',(0,0),(-1,0),'MIDDLE'),
        ('TEXTCOLOR',(0,0),(-1,0),colors.HexColor("#333")),
        ('LEFTPADDING',(0,0),(1,0),10),
        ('RIGHTPADDING',(0,0),(1,0),10),
        ('TOPPADDING',(0,0),(1,0),8),
        ('BOTTOMPADDING',(0,0),(1,0),8)
    ]))
    flow.append(header_table)
    flow.append(Spacer(1,12))

    # JDE uitgangssituatie
    flow.append(Paragraph("JDE uitgangssituatie", styles["JDESub"]))
    jde_scores_text=", ".join([f"{c}: {int(verwachte_scores_eigen.get(c,0))}" for c in criteria])
    flow.append(Paragraph(f"Prijspositie: {margin_pct:.1f}% duurder dan goedkoopste. Score-schaal: {scale_label}. Kwaliteitsscore(s): {jde_scores_text}.", styles["JDENormal"]))
    flow.append(Spacer(1,8))

    # Per-criterium table (JDE uitgangssituatie)
    crit_table_data=[["Criterium","Weging (%)","Max punten","JDE score","JDE raw pts","JDE contrib (van kwaliteit)"]]
    for c in criteria:
        wt=criterion_weights.get(c,0.0)
        mp=criterion_maxpoints.get(c,0.0)
        jde_score=verwachte_scores_eigen.get(c,0.0)
        jde_raw=jde_breakdown[c]["raw_points"]
        jde_contrib=jde_breakdown[c]["contribution"]
        crit_table_data.append([c,f"{wt:.1f}",f"{mp:.1f}",f"{int(jde_score)}",f"{jde_raw}",f"{jde_contrib}"])
    
    crit_tbl=Table(crit_table_data, colWidths=[140,70,70,70,80,100])
    crit_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#7A1F1F")), # Header bruin
        ('TEXTCOLOR',(0,0),(-1,0),colors.white), # Header tekst wit
        ('GRID',(0,0),(-1,-1),0.25,colors.HexColor("#FFFAF6")),
        ('FONTNAME',(0,0),(-1,0),'OswaldBold'),
        ('FONTNAME',(0,1),(-1,-1),'Aptos'), # Rest van de rijen Aptos
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(1,1),(-1,-1),'CENTER')
    ]))
    flow.append(crit_tbl)
    flow.append(Spacer(1,20))
    
    # Scenario overzicht table
    flow.append(Paragraph("Scenario overzicht", styles["JDESub"]))
    flow.append(Spacer(1,8))

    pdf_cols=["Scenario","Status","Verschil","Prijsactie","Kwaliteitsactie"]
    table_data=[pdf_cols]+[[r[col] for col in pdf_cols] for r in rows]
    
    t=Table(table_data,colWidths=[170,70,60,150,150])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#7A1F1F")), # Header bruin
        ('TEXTCOLOR',(0,0),(-1,0),colors.white), # Header tekst wit
        ('GRID',(0,0),(-1,-1),0.25,colors.HexColor("#FFFAF6")),
        ('FONTNAME',(0,0),(-1,0),'OswaldBold'),
        ('FONTNAME',(0,1),(-1,-1),'Aptos'), # Rest van de rijen Aptos
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(1,1),(2,-1),'CENTER'),
        # Alternerende rijkleuren voor leesbaarheid
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('BACKGROUND', (0, 2), (-1, -1), colors.HexColor("#F3F3F3")),
    ]))
    flow.append(t)
    flow.append(Spacer(1,10))

    # Adviesroutes
    flow.append(Paragraph("Adviesroutes", styles["JDESub"]))
    
    for r in rows:
        advies_str = f"<b>{r['Scenario']}</b>: {r['Prijsactie']}. {r['Kwaliteitsactie']}"
        flow.append(Paragraph(advies_str, styles["JDENormal"]))
        
    flow.append(Spacer(1,20))

    # Toelichting
    flow.append(Paragraph("Toelichting: BPKV (Beste Prijs-Kwaliteit Verhouding) weegt prijs en kwaliteit. Kwaliteitspunten worden verdeeld volgens de opgegeven weging; de puntentoekenning per criterium geeft aan hoe scores op de schaal naar punten worden geconverteerd. Gebruik deze one-pager als extra slide in presentaties.", styles["JDEItalic"]))

    # Afronding
    doc.build(flow)
    st.download_button("Download compacte PDF", data=pdf_buf.getvalue(), file_name="winkans_compact.pdf", mime="application/pdf")
