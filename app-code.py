import streamlit as st
import pandas as pd
import math
import io
import os

# ReportLab voor PDF
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

# ---------- Pagina & CSS (JDE-stijl) ----------
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');
h1,h2,h3,h4 {font-family:'Oswald',sans-serif!important;font-weight:700;color:#7A1F1F;}
html,body,.stApp {background-color:#F3E9DB;font-family:'Segoe UI','Aptos',sans-serif!important;color:#000;}
.stButton>button {font-family:'Oswald',sans-serif!important;font-weight:700;background:#7A1F1F;color:#fff;border-radius:6px;}
.stButton>button:hover {background:#4B2E2B;}
thead tr th {background:#C8A165!important;color:#fff!important;}
[data-testid="stSidebar"]>div:first-child {background:linear-gradient(180deg,#7A1F1F 0%,#4B2E2B 100%);color:#fff;}
[data-testid="stSidebar"] label {color:#fff!important;}
</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"    # wijnrood
ACCENT_GOLD   = "#C8A165"    # goudaccent
PAGE_BEIGE    = "#F3E9DB"    # beige achtergrond

# Herfstige statuskleuren (lichte tinten voor rijen)
WIN_ROW_BG    = colors.HexColor("#E6EBD8")  # licht mosgroen
LOSE_ROW_BG   = colors.HexColor("#EAD5D1")  # licht kastanje
DRAW_ROW_BG   = colors.HexColor("#EDE1C9")  # licht goud/beige

LOGO_PATH = os.path.join("assets","logo_jde.png")
BEANS_PATH = os.path.join("assets","beans.png")   # optioneel decor
LEAVES_PATH = os.path.join("assets","leaves.png") # optioneel decor

# ---------- Header ----------
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=120)
st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# ---------- Sidebar: methodiek & invoer ----------
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
kwaliteit_pct = st.sidebar.number_input("Kwaliteit (%)", 0, 100, 60, 1)
prijs_pct     = st.sidebar.number_input("Prijs (%)",     0, 100, 40, 1)

# Puntenschaal & criteria
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-2,5-5-7,5-10": [0,2.5,5,7.5,10],
    "0%-20%-40%-60%-80%-100%": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "Custom...": None
}
scale_label  = st.sidebar.selectbox("Kies een schaal", list(scales.keys()))
scale_values = scales[scale_label] if scale_label!="Custom..." else [
    float(x) for x in st.sidebar.text_input("Eigen schaal","0,25,50,75,100").split(",")
]
max_scale = max(scale_values)

criteria_raw = st.sidebar.text_input("Criterianamen (komma, min 2)", "Duurzaamheid,Service")
criteria     = [c.strip() for c in criteria_raw.split(",") if c.strip()]
max_points_criteria = {c: st.sidebar.number_input(f"Max punten {c}", 1, 200, 30) for c in criteria}
max_price_points    = st.sidebar.number_input("Max punten Prijs",    1, 200, 40)

st.sidebar.header("Stap 2: JDE inschatting")
verwachte_scores_eigen = {
    c: float(st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}"))
    for c in criteria
}
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (JDE)", 0.0, 100.0, 10.0, 0.1)

# ---------- Scenario invoer ----------
st.header("📥 Concurrentsituaties")
num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}"):
        naam        = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Concurrent is goedkoopste?", key=f"cheap{i}")
        comp_margin = 0.0 if is_cheapest else st.number_input("% duurder dan goedkoopste (conc.)", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}")
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam": naam, "marge": float(comp_margin), "is_cheapest": is_cheapest, "kval_scores": kval_scores})

# ---------- Helpers ----------
def score_to_points(s, maxp):
    return (float(s)/max_scale) * maxp

def compute_quality_points(scores_dict):
    return sum(score_to_points(scores_dict[c], max_points_criteria[c]) for c in criteria)

def absolute_price_points(marge, M):
    return M * (1 - marge/100.0)

def required_drop_piecewise(my_margin, comp_margin, Qm, Qc, M):
    """
    Minimale zakking (in %) om te WINNEN.
    Regime A (jij blijft duurder): m_req_A = c + (100/M)*(Qm - Qc)  [geldig als m_req_A >= c]
    Regime B (jij wordt goedkoopste): m_req_B = c - (100/M)*(Qc - Qm)
    """
    m_req_A = comp_margin + (100.0/M)*(Qm - Qc)
    m_req_B = comp_margin - (100.0/M)*(Qc - Qm)
    m_req   = m_req_A if m_req_A >= comp_margin else m_req_B
    drop    = max(0, my_margin - m_req)
    drop_int   = int(math.ceil(drop))  # naar boven afronden
    target_int = int(round(my_margin - drop_int))
    return drop_int, target_int

def points_per_step_for_criterion(c):
    """Correcte punten per stap: (max_points / max_scale) * stapgrootte (neem kleinste positieve stap)."""
    diffs = [scale_values[i+1]-scale_values[i] for i in range(len(scale_values)-1)]
    step_size = min([d for d in diffs if d > 0]) if diffs else 1
    return (max_points_criteria[c] / max_scale) * step_size

def advice_route_text(price_action, qual_action):
    """Bouw adviesroute op basis van acties (tekst onder tabel in PDF)."""
    p_needed = ("Verlaag" in price_action) and ("Geen actie nodig" not in price_action)
    q_needed = (qual_action not in ["-", "Ontoereikend", ""]) and ("Verhoog" in qual_action)
    if p_needed and q_needed:
        return "Adviesroute: prijs + kwaliteit"
    if p_needed and not q_needed:
        return "Adviesroute: prijs"
    if (not p_needed) and q_needed:
        return "Adviesroute: kwaliteit"
    return "Adviesroute: geen actie"

# ---------- Analyse & UI ----------
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # JDE steady punten
    jde_quality_pts = compute_quality_points(verwachte_scores_eigen)
    jde_price_pts   = absolute_price_points(margin_pct, max_price_points)
    jde_total       = jde_quality_pts + jde_price_pts

    rows = []
    # samenvattingscijfers
    win_no_action = 0
    win_price     = 0
    win_quality   = 0

    # voor globaal prijsadvies (strengste daling over alle concurrenten)
    global_drops = []

    for idx, s in enumerate(scenarios, start=1):
        comp_margin      = s["marge"]
        comp_quality_pts = compute_quality_points(s["kval_scores"])
        comp_price_pts   = absolute_price_points(comp_margin, max_price_points)
        comp_total       = comp_quality_pts + comp_price_pts

        status   = "WIN" if jde_total > comp_total else ("LOSE" if jde_total < comp_total else "DRAW")
        verschil = int(round(jde_total - comp_total))

        # Prijsactie
        drop_int, target_int = required_drop_piecewise(margin_pct, comp_margin, jde_quality_pts, comp_quality_pts, max_price_points)
        # Bij DRAW: minimaal 1%
        if status == "DRAW" and drop_int == 0:
            drop_int  = 1
            target_int = int(round(margin_pct - 1))
        prijsactie = "Geen actie nodig" if status=="WIN" else f"Verlaag {drop_int}% (naar {target_int}%)"
        if status!="WIN" and drop_int>0:
            win_price += 1
            global_drops.append(drop_int)
        elif status=="WIN":
            win_no_action += 1

        # Kwaliteitsactie (alleen tonen als kwaliteit alleen tot WIN leidt)
        qual_action = "-"
        if status!="WIN":
            found = False
            for c in criteria:
                cur = float(verwachte_scores_eigen[c])
                higher = [x for x in scale_values if float(x) > cur]
                for nxt in higher:
                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                    # kwaliteit alleen: prijs blijft gelijk
                    if (jde_quality_pts + gain + jde_price_pts) > (comp_total + 0.005):
                        qual_action = f"Verhoog {c} {int(round(cur))}→{int(round(nxt))} (+{int(round(gain))} ptn)"
                        win_quality += 1
                        found = True
                        break
                if found: break
            if not found:
                qual_action = "Ontoereikend"

        rows.append({
            "Scenario": f"{idx}. {s['naam']}",
            "Status": status,
            "Verschil": verschil,
            "JDE totaal": int(round(jde_total)),
            "Conc totaal": int(round(comp_total)),
            "JDE prijs": int(round(jde_price_pts)),
            "Conc prijs": int(round(comp_price_pts)),
            "JDE kwaliteit": int(round(jde_quality_pts)),
            "Conc kwaliteit": int(round(comp_quality_pts)),
            "Prijsactie": prijsactie,
            "Kwaliteitsactie": qual_action
        })

    df = pd.DataFrame(rows, columns=[
        "Scenario","Status","Verschil","JDE totaal","Conc totaal",
        "JDE prijs","Conc prijs","JDE kwaliteit","Conc kwaliteit",
        "Prijsactie","Kwaliteitsactie"
    ])
    st.dataframe(df, use_container_width=True)

    # ---------- Samenvatting (salesvriendelijk) ----------
    st.subheader("📊 Samenvatting")
    glob_adv_drop = max(global_drops) if global_drops else 0
    glob_adv_target = int(round(margin_pct - glob_adv_drop)) if glob_adv_drop>0 else int(round(margin_pct))

    st.markdown(f"""
- **Zonder actie win je:** **{win_no_action}** scenario's  
- **Winnen via prijs:** **{win_price}** scenario's  
- **Winnen via kwaliteit (zonder prijsverlaging):** **{win_quality}** scenario's  
- **Globaal prijsadvies (strengste concurrent):** verlaag **{glob_adv_drop}%** (naar **{glob_adv_target}%**)
""")

    st.markdown("**Punten per kwaliteitscriterium per stap:**")
    for c in criteria:
        pts_step = points_per_step_for_criterion(c)
        st.markdown(f"- {c}: {int(round(pts_step))} ptn per stap")

    # ---------- PDF Export (JDE-stijl one-pager) ----------
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buf, pagesize=landscape(A4),
        leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="JDETitle", parent=styles["Title"], textColor=colors.HexColor(PRIMARY_COLOR)))
    styles.add(ParagraphStyle(name="JDENormal", parent=styles["Normal"], textColor=colors.black))

    flow = []

    # Header (logo + titel)
    if os.path.exists(LOGO_PATH):
        flow.append(Image(LOGO_PATH, width=120, height=58))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["JDETitle"]))
    flow.append(Spacer(1, 10))

    # Samenvatting-blok
    flow.append(Paragraph(f"• Zonder actie win je {win_no_action} scenario's.", styles["JDENormal"]))
    flow.append(Paragraph(f"• In {win_price} scenario's kun je winnen door prijs te verlagen.", styles["JDENormal"]))
    flow.append(Paragraph(f"• In {win_quality} scenario's kun je winnen door kwaliteit te verbeteren (zonder prijsverlaging).", styles["JDENormal"]))
    flow.append(Paragraph(f"• Globaal prijsadvies: verlaag {glob_adv_drop}% (naar {glob_adv_target}%).", styles["JDENormal"]))
    flow.append(Spacer(1, 8))

    # Punten per criterium per stap
    flow.append(Paragraph("Punten per kwaliteitscriterium per stap:", styles["JDENormal"]))
    for c in criteria:
        pts_step = points_per_step_for_criterion(c)
        flow.append(Paragraph(f"- {c}: {int(round(pts_step))} ptn per stap", styles["JDENormal"]))
    flow.append(Spacer(1, 10))

    # Tabel
    table_data = [list(df.columns)] + df.values.tolist()

    # Zorg dat tabel past op landscape A4: total width ≈ 794pt
    col_widths = [80,55,55,60,60,60,60,70,70,105,124]  # som = 794

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    base_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('GRID',       (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
    ])
    t.setStyle(base_style)

    # Herfstige statuskleur per rij (na header)
    for i in range(1, len(table_data)):
        status_val = str(table_data[i][1]).upper()
        row_bg = DRAW_ROW_BG
        if status_val == "WIN":
            row_bg = WIN_ROW_BG
        elif status_val == "LOSE":
            row_bg = LOSE_ROW_BG
        # apply to whole row i (including all columns)
        t.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), row_bg)]))

    flow.append(t)
    flow.append(Spacer(1, 10))

    # Adviesroute onder tabel (tekstueel, per scenario)
    flow.append(Paragraph("Adviesroute per scenario:", styles["JDENormal"]))
    for i in range(len(df)):
        price_action = str(df.iloc[i]["Prijsactie"])
        qual_action  = str(df.iloc[i]["Kwaliteitsactie"])
        route_txt    = advice_route_text(price_action, qual_action)
        flow.append(Paragraph(f"- {df.iloc[i]['Scenario']}: {route_txt}", styles["JDENormal"]))
    flow.append(Spacer(1, 10))

    # Uitleg BPKV
    flow.append(Paragraph(
        "BPKV (Beste Prijs-Kwaliteit Verhouding) beoordeelt inschrijvingen op prijs en kwaliteit. "
        "Prijspunten zijn steady en kwaliteitspunten volgen de gekozen schaal. "
        "Adviezen zijn scenario-specifiek en objectief berekend.",
        styles["JDENormal"]
    ))

    # Beige pagina-achtergrond & optionele decor (beans/leaves)
    def draw_page_bg(canvas, doc):
        # Beige achtergrond
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(PAGE_BEIGE))
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
        canvas.restoreState()
        # Optionele decor in hoeken (klein en subtiel)
        try:
            if os.path.exists(BEANS_PATH):
                canvas.drawImage(BEANS_PATH, doc.pagesize[0]-80, 20, width=60, height=40, mask='auto')
            if os.path.exists(LEAVES_PATH):
                canvas.drawImage(LEAVES_PATH, 20, doc.pagesize[1]-80, width=60, height=40, mask='auto')
        except Exception:
            pass

    doc.build(flow, onFirstPage=draw_page_bg, onLaterPages=draw_page_bg)
    pdf_buf.seek(0)

    st.download_button("📄 Download PDF (JDE-stijl, one-pager)", pdf_buf, "advies_winkans_jde.pdf", mime="application/pdf")

else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
