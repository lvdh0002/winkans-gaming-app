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
h1,h2,h3,h4 { font-family: 'Oswald', sans-serif !important; font-weight:700; color:#7A1F1F; }
html,body,.stApp { background-color:#F3E9DB; font-family:'Segoe UI',sans-serif!important; color:#000; }
.stButton>button { font-family:'Oswald',sans-serif!important; font-weight:700; background:#7A1F1F; color:#fff; border-radius:6px; }
.stButton>button:hover { background:#4B2E2B; }
[data-testid="stSidebar"] > div:first-child { background:#A13D3B!important; color:#fff; }
[data-testid="stSidebar"] label { color:#fff!important; }
</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"
LOGO_PATH = os.path.join("assets", "logo_jde.png")

# Fonts registreren voor PDF (met fallback als bestanden ontbreken)
try:
    pdfmetrics.registerFont(TTFont("OswaldBold", os.path.join("assets", "Oswald-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Aptos", os.path.join("assets", "Aptos-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", os.path.join("assets", "Aptos-Italic.ttf")))
    FONTS_LOADED = True
except:
    # Fallback fonts als de .ttf bestanden er niet zijn
    pdfmetrics.registerFont(TTFont("OswaldBold", "Helvetica-Bold")) 
    pdfmetrics.registerFont(TTFont("Aptos", "Helvetica"))
    pdfmetrics.registerFont(TTFont("Aptos-Italic", "Helvetica-Oblique"))
    FONTS_LOADED = False
    st.warning("Let op: Font bestanden (Oswald/Aptos) niet gevonden in 'assets'. Standaard fonts worden gebruikt.")

# -------------------------
# SESSION STATE & CALLBACKS
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
if "criteria_data" not in st.session_state:
    st.session_state.criteria_data = []

# Callback functies voor automatische 100% som
def update_prijs():
    # Update kwaliteit op basis van nieuwe prijs
    st.session_state.kwaliteit_pct = 100 - st.session_state.prijs_pct

def update_kwaliteit():
    # Update prijs op basis van nieuwe kwaliteit
    st.session_state.prijs_pct = 100 - st.session_state.kwaliteit_pct

def sync_weight_max(i):
    # Callback: als weging verandert, zet max punten gelijk aan weging (tenzij handmatig overruled later)
    weight_key = f"crit_weight_{i}"
    max_key = f"crit_max_{i}"
    if weight_key in st.session_state:
        st.session_state[max_key] = st.session_state[weight_key]

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# -------------------------
# SIDEBAR - INSTELLINGEN
# -------------------------
st.sidebar.header("Beoordelingsmethodiek Instellingen")

# 1. Weging prijs en kwaliteit (gekoppeld)
col_p, col_q = st.sidebar.columns(2)
prijs_pct = col_p.number_input(
    "Weging prijs (%)",
    min_value=0, max_value=100,
    value=int(st.session_state.prijs_pct),
    step=1,
    key="prijs_pct",
    on_change=update_prijs
)
kwaliteit_pct = col_q.number_input(
    "Weging kwaliteit (%)",
    min_value=0, max_value=100,
    value=int(st.session_state.kwaliteit_pct),
    step=1,
    key="kwaliteit_pct",
    on_change=update_kwaliteit
)

# 2. Beoordelingsschaal
st.sidebar.subheader("Beoordelingsschaal kwaliteit")
scale_options = {
    "0-20-40-60-80-100": [0, 20, 40, 60, 80, 100],
    "0-25-50-75-100": [0, 25, 50, 75, 100],
    "Custom": None
}
selected_scale = st.sidebar.selectbox("Kies schaal", options=list(scale_options.keys()), index=0)
if selected_scale != "Custom":
    score_scale = scale_options[selected_scale]
else:
    custom_input = st.sidebar.text_input("Custom schaal (komma gescheiden)", "0,10,20,30,40,50,60,70,80,90,100")
    try:
        score_scale = [float(x.strip()) for x in custom_input.split(",") if x.strip()]
    except:
        score_scale = [0, 100]
st.session_state.score_scale = score_scale
scale_label = selected_scale if selected_scale != "Custom" else custom_input

# 3. Kwaliteitscriteria
num_criteria = st.sidebar.number_input("Aantal kwaliteitscriteria", 1, 10, len(st.session_state.criteria))

# Pas lijst met criteria namen aan indien aantal verandert
if len(st.session_state.criteria) < num_criteria:
    st.session_state.criteria += [f"Criteria {i+1}" for i in range(len(st.session_state.criteria), num_criteria)]
else:
    st.session_state.criteria = st.session_state.criteria[:num_criteria]

st.sidebar.subheader("Kwaliteitscriteria details")
criteria_data = []
default_weight = int(st.session_state.kwaliteit_pct / num_criteria) if num_criteria > 0 else 0

for i in range(num_criteria):
    st.sidebar.markdown(f"**Criterium {i+1}**")
    name = st.sidebar.text_input(f"Naam", value=st.session_state.criteria[i], key=f"crit_name_{i}")
    
    c1, c2 = st.sidebar.columns(2)
    # Weging input met callback naar sync functie
    weight = c1.number_input(
        f"Weging (%)", 
        min_value=0, max_value=100, 
        value=default_weight, 
        step=1, 
        key=f"crit_weight_{i}",
        on_change=sync_weight_max,
        args=(i,)
    )
    
    # Max punten input (value wordt geupdate via session_state key door sync_weight_max)
    # We gebruiken hier key=f"crit_max_{i}" die door de callback wordt aangestuurd
    if f"crit_max_{i}" not in st.session_state:
         st.session_state[f"crit_max_{i}"] = weight

    max_points = c2.number_input(
        f"Max punten", 
        min_value=1, max_value=200, 
        key=f"crit_max_{i}"
    )

    criteria_data.append({"name": name, "weight": weight, "max_points": max_points})

st.session_state.criteria_data = criteria_data

# Max punten prijs (standaard gelijk aan weging prijs)
st.sidebar.markdown("---")
max_price_points = st.sidebar.number_input("Max punten prijs", 1, 100, int(st.session_state.prijs_pct))

# -------------------------
# INPUT: EIGEN AANBOD & CONCURRENTEN
# -------------------------
st.sidebar.header("Jouw Aanbod (JDE)")
self_margin = st.sidebar.number_input("Jouw prijs (% duurder dan laagste)", 0.0, 200.0, 10.0, 0.1)
self_scores = {}
for cd in criteria_data:
    self_scores[cd['name']] = st.sidebar.selectbox(f"Jouw score: {cd['name']}", score_scale, index=len(score_scale)-1)

# Hoofdscherm Competitie
st.header("Concurrentiescenario's")
num_competitors = st.number_input("Aantal concurrenten", 1, 10, st.session_state.num_competitors)
st.session_state.num_competitors = num_competitors

scenarios = []
cols = st.columns(num_competitors)
for i in range(num_competitors):
    with cols[i]:
        st.subheader(f"Concurrent {i+1}")
        c_name = st.text_input(f"Naam conc. {i+1}", f"Concurrent {i+1}")
        is_cheap = st.checkbox("Is goedkoopste?", key=f"c_cheap_{i}")
        if is_cheap:
            c_margin = 0.0
            st.info("Marge: 0% (basis)")
        else:
            c_margin = st.number_input(f"% Duurder", 0.0, 200.0, 5.0, 0.1, key=f"c_marg_{i}")
        
        c_scores = {}
        for cd in criteria_data:
            c_scores[cd['name']] = st.selectbox(f"Score {cd['name']}", score_scale, index=0, key=f"c_score_{i}_{cd['name']}")
        
        scenarios.append({
            "naam": c_name,
            "marge": c_margin,
            "kval_scores": c_scores
        })

# -------------------------
# REKENLOGICA FUNCTIES
# -------------------------
def absolute_price_points(margin_pct, max_points):
    # Formule: Max punten * (1 - (marge/100 + drempel)). Hier simpel gehouden.
    # Aanname: bij 0% marge krijg je niet max punten, maar max - opslag?
    # Standaard formule in aanbestedingen varieert. 
    # Hier gebruiken we de logica uit je snippet: Max * (1 - (marge/100 + 0.01))
    # Dit betekent dat zelfs de goedkoopste (0%) 99% van de punten krijgt, of de formule is relatief.
    # We gebruiken de formule uit je eerdere snippet:
    pts = float(max_points) * (1.0 - (margin_pct/100.0))
    return max(0.0, pts)

def compute_quality_points_and_breakdown(scores_dict):
    breakdown = {}
    total_q = 0.0
    
    # Haal totalen op voor normalisatie indien nodig, hier gebruiken we absolute schalen uit input
    for crit in st.session_state.criteria_data:
        name = crit['name']
        weight = crit['weight']
        max_p = crit['max_points']
        
        score_val = float(scores_dict.get(name, 0))
        
        # Berekening: (Behaalde score / 100) * Max Punten Criterium * (Weging Criterium / Totaal Weging Kwaliteit)?
        # OF: De input is al "Max Punten" voor dat criterium in totaal?
        # Aanname: Max Punten in sidebar is de punten die je krijgt bij een 100 score.
        
        raw_points = (score_val / 100.0) * max_p
        
        # De weging in sidebar telt op tot bijv 60. 
        # Als max punten per criterium ook optellen tot 60, is raw_points direct de contributie.
        # Als max punten "10" is maar weging "20", is er een mismatch. 
        # We gebruiken hier de "Max punten" als de waarheid voor de score-impact.
        
        contribution = raw_points 
        
        breakdown[name] = {
            "raw_points": round(raw_points, 2),
            "contribution": round(contribution, 2)
        }
        total_q += contribution
        
    return total_q, breakdown

def determine_status_and_actions(j_tot, j_q, j_p, c_tot, c_q, c_p, j_marg, c_marg):
    diff = j_tot - c_tot
    if diff > 0:
        return "WIN", "Behoud prijsstrategie", "Kwaliteit borgen", int(diff)
    elif diff < 0:
        status = "VERLIES"
        # Actie bepalen
        p_actie = "Verlaag prijs" if j_p < c_p else "Prijs is competitief"
        k_actie = "Verbeter kwaliteit" if j_q < c_q else "Kwaliteit is leidend"
        
        if j_marg > c_marg and (c_p - j_p) > (c_q - j_q):
            p_actie = f"Marge verlagen (nu {j_marg}%)"
        
        return status, p_actie, k_actie, int(diff)
    else:
        return "GELIJK", "Kijk naar details", "Kijk naar details", 0

# -------------------------
# GENERATE PDF & RESULTS
# -------------------------
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # Berekeningen JDE
    jde_q_total, jde_breakdown = compute_quality_points_and_breakdown(self_scores)
    jde_p = absolute_price_points(self_margin, max_price_points)
    jde_total = jde_q_total + jde_p
    
    rows = []
    
    for idx, s in enumerate(scenarios, start=1):
        comp_q_total, comp_breakdown = compute_quality_points_and_breakdown(s["kval_scores"])
        comp_p = absolute_price_points(s["marge"], max_price_points)
        comp_total = comp_q_total + comp_p
        
        status, prijsactie, kwalactie, verschil = determine_status_and_actions(
            jde_total, jde_q_total, jde_p, 
            comp_total, comp_q_total, comp_p, 
            self_margin, s["marge"]
        )
        
        row = {
            "Scenario": f"{idx}. {s['naam']}",
            "Status": status,
            "Verschil": verschil,
            "JDE totaal": round(jde_total, 2),
            "JDE prijs pts": round(jde_p, 2),
            "JDE kwal pts": round(jde_q_total, 2),
            "Conc totaal": round(comp_total, 2),
            "Conc prijs pts": round(comp_p, 2),
            "Conc kwal pts": round(comp_q_total, 2),
            "Prijsactie": prijsactie,
            "Kwaliteitsactie": kwalactie
        }
        
        # Voeg details toe voor CSV/Excel export
        for c in st.session_state.criteria_data:
            name = c['name']
            row[f"JDE {name}"] = jde_breakdown[name]["raw_points"]
            row[f"Conc {name}"] = comp_breakdown[name]["raw_points"]
            
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    # Toon tabel op scherm (compact)
    display_cols = ["Scenario", "Status", "Verschil", "JDE totaal", "Conc totaal", "Prijsactie", "Kwaliteitsactie"]
    st.dataframe(df[display_cols], use_container_width=True)
    
    # Download CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download volledige data (CSV)", data=csv_bytes, file_name="winkans_export.csv", mime="text/csv")
    
    # -------------------------
    # PDF GENERATIE (REPORTLAB)
    # -------------------------
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buf, 
        pagesize=landscape(A4),
        leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
    )
    
    styles = getSampleStyleSheet()
    # Styles definiëren
    styles.add(ParagraphStyle(name="JDETitle", fontName="OswaldBold", fontSize=20, leading=24, textColor=colors.HexColor("#7A1F1F")))
    styles.add(ParagraphStyle(name="JDESub", fontName="OswaldBold", fontSize=12, leading=14, textColor=colors.HexColor("#333")))
    styles.add(ParagraphStyle(name="JDENormal", fontName="Aptos", fontSize=10, leading=13, textColor=colors.HexColor("#333")))
    # HIER DE GEVRAAGDE AANPASSING: Aptos-Italic
    styles.add(ParagraphStyle(name="JDEItalic", fontName="Aptos-Italic", fontSize=9, leading=11, textColor=colors.HexColor("#666")))

    flow = []

    # 1. Header met Logo
    if os.path.exists(LOGO_PATH):
        try:
            img_reader = ImageReader(LOGO_PATH)
            iw, ih = img_reader.getSize()
            logo_width = 100
            logo_height = logo_width * (ih / iw)
            logo = Image(LOGO_PATH, width=logo_width, height=logo_height)
        except:
            logo = Paragraph("<b>JDE</b>", styles["JDETitle"])
    else:
        logo = Paragraph("<b>JDE</b>", styles["JDETitle"])

    header_data = [[logo, Paragraph("Advies: Winkans & Acties — BPKV", styles["JDETitle"])]]
    header_table = Table(header_data, colWidths=[120, 500])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    flow.append(header_table)
    flow.append(Spacer(1, 20))

    # 2. Uitgangssituatie
    flow.append(Paragraph("JDE Uitgangssituatie", styles["JDESub"]))
    
    jde_score_txt = ", ".join([f"{k}: {v}" for k, v in self_scores.items()])
    summary_text = f"""
    <b>Weging:</b> Prijs {st.session_state.prijs_pct}%, Kwaliteit {st.session_state.kwaliteit_pct}%.<br/>
    <b>JDE Prijsmarge:</b> {self_margin}% boven laagste.<br/>
    <b>JDE Scores:</b> {jde_score_txt}.
    """
    flow.append(Paragraph(summary_text, styles["JDENormal"]))
    flow.append(Spacer(1, 15))

    # 3. Kwaliteit Details Tabel
    flow.append(Paragraph("Kwaliteitscriteria Breakdown", styles["JDESub"]))
    crit_headers = ["Criterium", "Weging", "Max Pts", "JDE Score", "JDE Pts"]
    crit_rows = [crit_headers]
    for c in st.session_state.criteria_data:
        crit_rows.append([
            c['name'], 
            str(c['weight']), 
            str(c['max_points']), 
            str(self_scores.get(c['name'], 0)), 
            str(jde_breakdown[c['name']]['raw_points'])
        ])
    
    c_table = Table(crit_rows, colWidths=[200, 80, 80, 80, 80], hAlign='LEFT')
    c_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F3E9DB")),
        ('FONTNAME', (0,0), (-1,0), "OswaldBold"),
        ('FONTNAME', (0,1), (-1,-1), "Aptos"),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#7A1F1F")),
    ]))
    flow.append(c_table)
    flow.append(Spacer(1, 15))

    # 4. Resultaten Scenarios
    flow.append(Paragraph("Scenario Resultaten", styles["JDESub"]))
    
    res_headers = ["Scenario", "Status", "JDE Tot", "Conc Tot", "Prijsactie", "Kwaliteitsactie"]
    res_data = [res_headers]
    for r in rows:
        res_data.append([
            r["Scenario"], 
            r["Status"], 
            str(r["JDE totaal"]), 
            str(r["Conc totaal"]), 
            r["Prijsactie"], 
            r["Kwaliteitsactie"]
        ])
        
    r_table = Table(res_data, colWidths=[150, 60, 60, 60, 180, 180], hAlign='LEFT')
    r_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7A1F1F")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), "OswaldBold"),
        ('FONTNAME', (0,1), (-1,-1), "Aptos"),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    flow.append(r_table)
    flow.append(Spacer(1, 30))

    # 5. Disclaimer / Footer (Met Aptos-Italic)
    disclaimer_text = "Deze berekening is een indicatie op basis van ingevoerde aannames. Aan deze uitkomsten kunnen geen rechten worden ontleend."
    flow.append(Paragraph(disclaimer_text, styles["JDEItalic"]))

    # Build PDF
    doc.build(flow)
    pdf_buf.seek(0)
    
    st.download_button(
        label="Download PDF Rapport",
        data=pdf_buf,
        file_name="Winkans_Rapport_JDE.pdf",
        mime="application/pdf"
    )
