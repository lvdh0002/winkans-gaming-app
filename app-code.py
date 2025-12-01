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

# -------------------------
# RESULTATEN & PDF
# -------------------------
st.header("Resultaten & Advies")

if st.button("Bereken winkansen"):
    jde_q, jde_brk = compute_quality_points(self_scores)
    jde_p = absolute_price_points(self_margin, max_price_points)
    jde_tot = jde_q + jde_p
    
    rows = []
    
    for idx, s in enumerate(scenarios, start=1):
        c_q, c_brk = compute_quality_points(s["kval_scores"])
        c_p = absolute_price_points(s["marge"], max_price_points)
        c_tot = c_q + c_p
        
        status, prijs_advies, verschil = calculate_precise_advice(
            jde_tot, jde_q, self_margin, c_tot, max_price_points
        )
        
        row = {
            "Scenario": s['naam'],
            "Status": status,
            "Advies Prijs": prijs_advies,
            "Score Verschil": verschil,
            "JDE Totaal": round(jde_tot, 2),
            "Conc Totaal": round(c_tot, 2),
            "JDE Kwaliteit": round(jde_q, 2),
            "Conc Kwaliteit": round(c_q, 2)
        }
        for k, v in jde_brk.items(): row[f"JDE {k}"] = round(v, 2)
        for k, v in c_brk.items(): row[f"Conc {k}"] = round(v, 2)
            
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    st.dataframe(
        df[["Scenario", "Status", "Score Verschil", "Advies Prijs", "JDE Totaal", "Conc Totaal"]], 
        use_container_width=True,
        column_config={
            "Advies Prijs": st.column_config.TextColumn("Direct Advies", width="large"),
        }
    )
    
    # PDF Generatie
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="JDETitle", fontName="OswaldBold", fontSize=20, textColor=colors.HexColor("#7A1F1F")))
    styles.add(ParagraphStyle(name="JDENormal", fontName="Aptos", fontSize=10))
    styles.add(ParagraphStyle(name="JDEItalic", fontName="Aptos-Italic", fontSize=9, textColor=colors.HexColor("#666")))

    flow = []
    logo = Image(LOGO_PATH, width=100, height=50) if os.path.exists(LOGO_PATH) else Paragraph("<b>JDE</b>", styles["JDETitle"])
    tbl = Table([[logo, Paragraph("Advies: Winkans & Acties", styles["JDETitle"])]], colWidths=[120, 500])
    tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    flow.append(tbl)
    flow.append(Spacer(1, 20))

    flow.append(Paragraph(f"<b>Uitgangssituatie:</b> Prijs weging {prijs_pct}%, Kwaliteit {kwaliteit_pct}%. Eigen marge: {self_margin}%.", styles["JDENormal"]))
    flow.append(Spacer(1, 15))

    headers = ["Scenario", "Status", "Verschil", "Prijs Advies", "JDE Tot", "Conc Tot"]
    data = [headers]
    for r in rows:
        data.append([r["Scenario"], r["Status"], str(r["Score Verschil"]), r["Advies Prijs"], str(r["JDE Totaal"]), str(r["Conc Totaal"])])
    
    t = Table(data, colWidths=[120, 60, 50, 250, 60, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#7A1F1F")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),"OswaldBold"),
        ('FONTNAME',(0,1),(-1,-1),"Aptos"),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(2,1),(-1,-1),'CENTER'),
        ('WORDWRAP',(0,0),(-1,-1),True)
    ]))
    flow.append(t)
    flow.append(Spacer(1, 30))
    flow.append(Paragraph("Deze berekening is indicatief.", styles["JDEItalic"]))
    
    doc.build(flow)
    st.download_button("Download PDF Rapport", pdf_buf.getvalue(), "winkans_advies.pdf", "application/pdf")
