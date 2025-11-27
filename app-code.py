import streamlit as st
import pandas as pd
import math
import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
from reportlab.lib.utils import ImageReader

# -------------------------
# Session state: prijs/kwaliteit sync
# -------------------------
if "prijs_pct" not in st.session_state:
    st.session_state.prijs_pct = 40
if "kwaliteit_pct" not in st.session_state:
    st.session_state.kwaliteit_pct = 60

def update_prijs():
    # called when prijs_pct changed
    st.session_state.kwaliteit_pct = 100 - st.session_state.prijs_pct

def update_kwaliteit():
    # called when kwaliteit_pct changed
    st.session_state.prijs_pct = 100 - st.session_state.kwaliteit_pct

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
LOGO_PATH = os.path.join("assets","logo_jde.png")  # zorg dat dit pad klopt

# Logo display in UI
if os.path.exists(LOGO_PATH):
    try:
        img_reader = ImageReader(LOGO_PATH)
        iw, ih = img_reader.getSize()
        logo_width = 120
        logo_height = logo_width * (ih / iw)
        st.image(LOGO_PATH, width=logo_width)
    except Exception:
        st.image(LOGO_PATH, width=100)
else:
    logo = Paragraph("", styles["JDENormal"])

st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# -------------------------
# Sidebar inputs
# -------------------------
st.sidebar.header("Stap 1: Beoordelingsmethodiek")

# Prijs & Kwaliteit inputs (geen slider) — synched
st.sidebar.number_input("Prijs (%)", min_value=0, max_value=100, key="prijs_pct", on_change=update_prijs)
st.sidebar.number_input("Kwaliteit (%)", min_value=0, max_value=100, key="kwaliteit_pct", on_change=update_kwaliteit)

prijs_pct = st.session_state.prijs_pct
kwaliteit_pct = st.session_state.kwaliteit_pct

st.sidebar.markdown(f"**Opmerking:** prijs + kwaliteit = **{prijs_pct + kwaliteit_pct}** (altijd 100)")

# Score schaal
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
    raw = st.sidebar.text_input("Eigen schaal (comma separated)", "0,25,50,75,100")
    try:
        scale_values = [float(x.strip()) for x in raw.split(",") if x.strip() != ""]
        if len(scale_values) < 2:
            st.sidebar.error("Custom schaal: minstens 2 waarden vereist. Gebruik standaard.")
            scale_values = [0,25,50,75,100]
    except:
        st.sidebar.error("Kon custom schaal niet parsen. Gebruik standaard.")
        scale_values = [0,25,50,75,100]

max_scale = max(scale_values)

# Criteria names
criteria_input = st.sidebar.text_input("Criterianamen (komma-gescheiden)", "Duurzaamheid,Service")
criteria = [c.strip() for c in criteria_input.split(",") if c.strip()]
if not criteria:
    st.sidebar.error("Voeg minstens één criterium toe.")

# For each criterion: weighting (%) and max points
st.sidebar.markdown("### Per criterium: weging (%) & max punten (puntentoekenning)")
criterion_weights = {}
criterion_maxpoints = {}
for c in criteria:
    st.sidebar.markdown(f"**{c}**")
    w = st.sidebar.number_input(f"Weging {c} (%)", min_value=0.0, max_value=100.0, value=round(100.0/len(criteria),1), step=0.5, key=f"w_{c}")
    p = st.sidebar.number_input(f"Max punten {c}", min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key=f"p_{c}")
    criterion_weights[c] = float(w)
    criterion_maxpoints[c] = float(p)

# Validate weight sum (if not 100, normalize when computing weight fractions)
sum_weights = sum(criterion_weights.values()) if len(criterion_weights)>0 else 0.0
if sum_weights == 0 and len(criterion_weights)>0:
    # avoid division by zero: set equal weights
    for c in criterion_weights:
        criterion_weights[c] = 100.0/len(criterion_weights)
    sum_weights = 100.0

# Max price points = prijs_pct (as requested)
max_price_points = float(prijs_pct)

# JDE expected scores per criterion (on the chosen scale)
verwachte_scores_eigen = {}
for c in criteria:
    sel = st.sidebar.selectbox(f"Score JDE voor {c}", [str(x) for x in scale_values], key=f"jde_score_{c}")
    try:
        verwachte_scores_eigen[c] = float(sel)
    except:
        verwachte_scores_eigen[c] = float(scale_values[0])

# margin of JDE relative to cheapest
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (JDE)", min_value=0.0, max_value=100.0, value=10.0, step=0.1)

# -------------------------
# Scenarios input
# -------------------------
st.header("📥 Concurrentsituaties")
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
            try:
                kval_scores[c] = float(sel)
            except:
                kval_scores[c] = float(scale_values[0])
        scenarios.append({"naam": naam or f"Concurrent {i+1}", "marge": float(marge), "kval_scores": kval_scores})

# -------------------------
# Helper functions & core math
# -------------------------
def score_to_raw_points(score, max_points_for_criterion):
    """Converts a scale score to raw points out of the criterion's max points."""
    try:
        return (float(score) / float(max_scale)) * float(max_points_for_criterion)
    except:
        return 0.0

def compute_quality_points_and_breakdown(scores: dict):
    """
    Returns:
      total_quality_points (float) -- sum of weighted contributions, max = kwaliteit_pct
      breakdown (dict) per criterion: { 'raw_points':..., 'normalized':..., 'weight_frac':..., 'contribution':... }
    """
    breakdown = {}
    total = 0.0
    for c in criteria:
        maxp = criterion_maxpoints.get(c, 0.0)
        raw = score_to_raw_points(scores.get(c, 0.0), maxp)  # 0..maxp
        norm = (raw / maxp) if maxp > 0 else 0.0  # 0..1
        weight_frac = (criterion_weights.get(c, 0.0) / sum_weights) if sum_weights > 0 else (1.0/len(criteria))
        # contribution scaled to kwaliteit_pct budget
        contribution = weight_frac * kwaliteit_pct * norm
        breakdown[c] = {
            "raw_points": round(raw, 2),
            "normalized": round(norm, 4),
            "weight_frac": round(weight_frac,4),
            "contribution": round(contribution, 4)
        }
        total += contribution
    # total is within (0 .. kwaliteit_pct)
    return total, breakdown

def absolute_price_points(marge, M):
    """Return price points out of max price points (M)."""
    return float(M) * (1.0 - float(marge) / 100.0)

def required_drop_piecewise(my_margin, comp_margin, Qm, Qc, M):
    """
    Using your original piecewise-ish logic to find minimal % drop to win.
    Returns (drop_int, target_int) where drop_int is integer % to drop and target_int is the new margin.
    """
    try:
        m_req_A = comp_margin + (100.0 / M) * (Qm - Qc)
        m_req_B = comp_margin - (100.0 / M) * (Qc - Qm)
        m_req = m_req_A if m_req_A >= comp_margin else m_req_B
        drop = max(0.0, my_margin - m_req)
        drop_int = int(math.ceil(drop))
        target_int = int(round(my_margin - drop_int))
        return drop_int, target_int
    except Exception:
        return 0, int(round(my_margin))

def determine_status_and_actions(jde_total, jde_q, jde_p, comp_total, comp_q, comp_p, my_margin, comp_margin):
    """
    Returns status ('WIN','LOSE','DRAW'), prijsactie str, kwaliteitsactie str
    and drop_int (int) used for price action.
    """
    eps = 1e-9
    if jde_total > comp_total + eps:
        status = "WIN"
    elif jde_total < comp_total - eps:
        status = "LOSE"
    else:
        status = "DRAW"

    drop_int, target_int = required_drop_piecewise(my_margin, comp_margin, jde_q, comp_q, max_price_points)
    # For DRAW or LOSE, if drop_int == 0 then we want minimal 1% to try to win
    if status != "WIN" and drop_int == 0:
        drop_int = 1
        target_int = int(round(my_margin - 1))

    prijsactie = "Geen actie nodig" if status == "WIN" else f"Verlaag {drop_int}% (naar {target_int}%)"

    # Qualitäts action: try to find single-step improvement on any criterion using the scale steps
    qual_action = "-"
    if status != "WIN":
        found = False
        for c in criteria:
            cur = float(verwachte_scores_eigen.get(c, 0.0))
            higher = [x for x in scale_values if float(x) > cur]
            for nxt in higher:
                # compute gain in quality-contribution if JDE increase c from cur -> nxt
                # Recompute raw & normalized for this criterion only
                maxp = criterion_maxpoints.get(c, 0.0)
                raw_cur = score_to_raw_points(cur, maxp)
                raw_nxt = score_to_raw_points(nxt, maxp)
                norm_cur = (raw_cur / maxp) if maxp>0 else 0.0
                norm_nxt = (raw_nxt / maxp) if maxp>0 else 0.0
                weight_frac = (criterion_weights.get(c, 0.0) / sum_weights) if sum_weights>0 else (1.0/len(criteria))
                contrib_cur = weight_frac * kwaliteit_pct * norm_cur
                contrib_nxt = weight_frac * kwaliteit_pct * norm_nxt
                gain = contrib_nxt - contrib_cur  # points (out of kwaliteit_pct budget)
                # if that gain makes total > competitor
                if (jde_q + gain + jde_p) > (comp_total + 1e-6):
                    qual_action = f"Verhoog {c} {int(round(cur))}→{int(round(nxt))} (+{round(gain,2)} ptn)"
                    found = True
                    break
            if found:
                break
        if not found:
            qual_action = "Ontoereikend"

    return status, prijsactie, qual_action, drop_int

def advice_route_text(price_action, qual_action):
    p_needed = ("Verlaag" in price_action) and ("Geen actie nodig" not in price_action)
    q_needed = (qual_action not in ["-", "Ontoereikend", ""]) and ("Verhoog" in qual_action)
    if p_needed and q_needed: return "Adviesroute: prijs + kwaliteit"
    if p_needed and not q_needed: return "Adviesroute: prijs"
    if (not p_needed) and q_needed: return "Adviesroute: kwaliteit"
    return "Adviesroute: geen actie"

# -------------------------
# Run analysis & UI output
# -------------------------
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # Compute JDE quality contributions & breakdown
    jde_q_total, jde_breakdown = compute_quality_points_and_breakdown(verwachte_scores_eigen)
    # price points
    jde_p = absolute_price_points(margin_pct, max_price_points)
    jde_total = jde_q_total + jde_p

    rows = []
    # For showing a detailed per-criterion table in the app we will build per-row breakdown as well
    for idx, s in enumerate(scenarios, start=1):
        comp_q_total, comp_breakdown = compute_quality_points_and_breakdown(s["kval_scores"])
        comp_p = absolute_price_points(s["marge"], max_price_points)
        comp_total = comp_q_total + comp_p

        status, prijsactie, kwalactie, drop_int = determine_status_and_actions(jde_total, jde_q_total, jde_p, comp_total, comp_q_total, comp_p, margin_pct, s["marge"])

        verschil = int(round(jde_total - comp_total))

        # Build a row with per-criterion raw & contrib info flattened (for ease of CSV export)
        row = {
            "Scenario": f"{idx}. {s['naam']}",
            "Status": status,
            "Verschil": verschil,
            "JDE totaal": round(jde_total,2),
            "JDE prijs pts": round(jde_p,2),
            "JDE kwaliteit pts (totaal)": round(jde_q_total,2),
            "Conc totaal": round(comp_total,2),
            "Conc prijs pts": round(comp_p,2),
            "Conc kwaliteit pts (totaal)": round(comp_q_total,2),
            "Prijsactie": prijsactie,
            "Kwaliteitsactie": kwalactie
        }

        # Add per-criterion details: raw and contribution for JDE and competitor
        for c in criteria:
            row[f"JDE {c} raw_pts"] = jde_breakdown[c]["raw_points"]
            row[f"JDE {c} contrib"] = jde_breakdown[c]["contribution"]
            row[f"Conc {c} raw_pts"] = comp_breakdown[c]["raw_points"]
            row[f"Conc {c} contrib"] = comp_breakdown[c]["contribution"]

        rows.append(row)

    df = pd.DataFrame(rows)
    st.subheader("Volledige resultaten (inclusief per-criterium breakdown)")
    st.dataframe(df, use_container_width=True)

    # Provide CSV download of full table
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download volledige resultaten (CSV)", data=csv_bytes, file_name="winkans_volledig.csv", mime="text/csv")

    # -------------------------
    # Build compact PDF one-pager
    # -------------------------
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()

    # Title style (Helvetica-Bold used)
    styles.add(ParagraphStyle(name="JDETitle", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor(PRIMARY_COLOR)))
    styles.add(ParagraphStyle(name="JDESub", fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#333")))
    styles.add(ParagraphStyle(name="JDENormal", fontName="Helvetica", fontSize=10, leading=13, textColor=colors.black))
    styles.add(ParagraphStyle(name="JDEItalic", fontName="Helvetica-Oblique", fontSize=9, leading=11, textColor=colors.HexColor("#444")))

    flow = []

    # Header bar: left logo + title + sustainability tagline
    header_data = []
    if os.path.exists(LOGO_PATH):
        try:
            img_reader = ImageReader(LOGO_PATH)
            iw, ih = img_reader.getSize()
            # set desired header logo width and compute height to preserve aspect
            logo_width = 120
            logo_height = logo_width * (ih / iw)
            logo = Image(LOGO_PATH, width=logo_width, height=logo_height)
        except Exception:
            # fallback: fixed small image
            logo = Image(LOGO_PATH, width=100, height=30)
    else:
        logo = Paragraph("", styles["JDENormal"])

    # Header title + tagline
    title_par = Paragraph("Advies: Winkans & Acties — BPKV", styles["JDETitle"])
    tagline = Paragraph("<b>Sustainability • Quality • People</b><br/>Een korte one-pager ter ondersteuning van je presentatie.", styles["JDENormal"])

    header_table = Table([[logo, Paragraph("Advies: Winkans & Acties — BPKV", styles["JDETitle"])]], colWidths=[logo_width + 8, 500])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(PRIMARY_COLOR)),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('LEFTPADDING',(0,0),(1,0),10),
        ('RIGHTPADDING',(0,0),(1,0),10),
        ('TOPPADDING',(0,0),(1,0),8),
        ('BOTTOMPADDING',(0,0),(1,0),8),
    ]))
    flow.append(header_table)
    flow.append(Spacer(1, 12))

    # JDE uitgangssituatie
    flow.append(Paragraph("JDE uitgangssituatie", styles["JDESub"]))
    jde_scores_text = ", ".join([f"{c}: {int(verwachte_scores_eigen.get(c,0))}" for c in criteria])
    flow.append(Paragraph(f"Prijspositie: {margin_pct:.1f}% duurder dan goedkoopste (JDE).  "
                          f"Score-schaal: {scale_label}.  Kwaliteitsscore(s): {jde_scores_text}.", styles["JDENormal"]))
    flow.append(Spacer(1, 8))

    # Per-criterium compact table (show weight, max points, JDE raw & contribution)
    crit_table_data = [["Criterium","Weging (%)","Max punten","JDE score","JDE raw pts","JDE contrib (van kwaliteit)"]]
    for c in criteria:
        wt = criterion_weights.get(c,0.0)
        mp = criterion_maxpoints.get(c,0.0)
        jde_score = verwachte_scores_eigen.get(c,0.0)
        jde_raw = jde_breakdown[c]["raw_points"] if 'jde_breakdown' in locals() and c in jde_breakdown else compute_quality_points_and_breakdown(verwachte_scores_eigen)[1][c]["raw_points"]
        jde_contrib = jde_breakdown[c]["contribution"]
        crit_table_data.append([c, f"{wt:.1f}", f"{mp:.1f}", f"{int(jde_score)}", f"{jde_raw}", f"{jde_contrib}"])

    crit_tbl = Table(crit_table_data, colWidths=[140,70,70,70,80,100])
    crit_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR',(0,0),(-1,0), colors.white),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(1,1),(-1,-1),'CENTER'),
    ]))
    flow.append(crit_tbl)
    flow.append(Spacer(1, 10))

    # Compact scenarios table (only key columns)
    flow.append(Paragraph("Scenario overzicht", styles["JDESub"]))
    pdf_cols = ["Scenario","Status","Verschil","Prijsactie","Kwaliteitsactie"]
    table_data = [pdf_cols] + [[r[col] for col in pdf_cols] for r in rows]
    t = Table(table_data, colWidths=[170,70,60,150,150])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR',(0,0),(-1,0), colors.white),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
    ]))
    # color rows based on status
    for i in range(1, len(table_data)):
        stt = str(table_data[i][1]).upper()
        bg = colors.HexColor("#EDE1C9")  # draw neutral
        if stt == "WIN":
            bg = colors.HexColor("#E6EBD8")
        elif stt == "LOSE":
            bg = colors.HexColor("#EAD5D1")
        t.setStyle(TableStyle([('BACKGROUND',(0,i),(-1,i),bg)]))
    flow.append(t)
    flow.append(Spacer(1, 10))

    # Advice routes & footnote
    flow.append(Paragraph("Adviesroutes", styles["JDESub"]))
    for r in rows:
        route = advice_route_text(r["Prijsactie"], r["Kwaliteitsactie"])
        flow.append(Paragraph(f"- {r['Scenario']}: {route} — {r['Prijsactie']}; {r['Kwaliteitsactie']}", styles["JDENormal"]))

    flow.append(Spacer(1, 8))
    flow.append(Paragraph("Toelichting: BPKV (Beste Prijs-Kwaliteit Verhouding) weegt prijs en kwaliteit. "
                          "Kwaliteitspunten worden verdeeld volgens de opgegeven weging; de puntentoekenning per criterium "
                          "geeft aan hoe scores op de schaal naar punten worden geconverteerd. Gebruik deze one-pager als extra slide in presentaties.", styles["JDEItalic"]))

    # Background painter
    def draw_bg(canvas, doc):
        canvas.setFillColor(colors.HexColor(PAGE_BEIGE))
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)

    doc.build(flow, onFirstPage=draw_bg)
    pdf_buf.seek(0)

    # Download button
    st.download_button("📄 Download compacte JDE one-pager (PDF)", data=pdf_buf.getvalue(), file_name="winkans_onepager.pdf", mime="application/pdf")

    st.success("Analyse voltooid — download de compacte one-pager of exporteer de volledige data (CSV) voor verdere verwerking.")
else:
    st.info("Klik op 'Bereken winkansen' om de analyse uit te voeren en de PDF te genereren.")
