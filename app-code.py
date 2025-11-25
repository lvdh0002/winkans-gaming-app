
import streamlit as st
import pandas as pd
import numpy as np
import io
import os

# --- Robust imports (met fallbacks) ---
HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except Exception:
    HAS_MPL = False

HAS_RL = True
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.utils import ImageReader
except Exception:
    HAS_RL = False

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
st.markdown(
    """
    https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap
    """,
    unsafe_allow_html=True,
)

# --- JDE Professional Huisstijl (beige/lichtbruin + wijnrood) ---
PRIMARY_COLOR = "#7A1F1F"    # wijnrood (donkerrood)
SECONDARY_BROWN = "#4B2E2B"  # koffiebruin
ACCENT_BEIGE = "#F3E9DB"     # beige / lichtbruin
ACCENT_GOLD  = "#C8A165"     # goudaccent

QUALITY_COLOR = "#2E7D32"    # donkergroen (kwaliteit)
PRICE_COLOR   = "#1565C0"    # donkerblauw (prijs)

LOGO_PATH = os.path.join("assets", "logo_jde.png")

# App-brede CSS

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');

html, body, .stApp {
    font-family: 'Oswald', Arial, sans-serif;
}

h1, h2, h3, h4 {
    font-family: 'Oswald', Arial, sans-serif;
    font-weight: 700;
    color: #7A1F1F; /* wijnrood */
}

.stButton>button {
    font-family: 'Oswald', Arial, sans-serif;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<style>
html, body, .stApp {{
  background-color: {ACCENT_BEIGE};
  font-family: Arial, Helvetica, sans-serif;
}}
h1, h2, h3, h4 {{
  color: {PRIMARY_COLOR};
  font-family: 'Oswald', Arial, Helvetica, sans-serif;
  letter-spacing: 0.2px;
}}
/* Sidebar headerband (wijnrood balk) */
[data-testid="stSidebar"] > div:first-child {{
  background: linear-gradient(180deg, {PRIMARY_COLOR} 0%, {SECONDARY_BROWN} 100%);
  color: #fff;
}}
/* Sidebar content */
[data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stNumberInput label, [data-testid="stSidebar"] .stSelectbox label {{
  color: #fff !important;
}}
/* Buttons */
.stButton>button {{
  background-color: {PRIMARY_COLOR};
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.6rem 1rem;
  font-weight: 700;
}}
.stButton>button:hover {{
  background-color: {SECONDARY_BROWN};
  color: #fff;
}}
/* Tabellen */
thead tr th {{
  background-color: {ACCENT_GOLD} !important;
  color: #fff !important;
}}
tbody tr td {{
  color: {SECONDARY_BROWN} !important;
}}
/* Expander header */
.streamlit-expanderHeader {{
  color: {SECONDARY_BROWN} !important;
  font-weight: 700;
}}
</style>
""", unsafe_allow_html=True)

# Titel + logo
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
with col_title:
    st.title("Tool om winkansen te berekenen o.b.v. BPKV (Beste Prijs Kwaliteit Verhouding)")

# --- Sidebar: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")

def _sync_from_quality():
    st.session_state.price_input = max(0, 100 - st.session_state.quality_input)

def _sync_from_price():
    st.session_state.quality_input = max(0, 100 - st.session_state.price_input)

col1, col2 = st.sidebar.columns(2)
with col1:
    st.number_input("Kwaliteit (%)", 0, 100, 60, 1, key="quality_input", on_change=_sync_from_quality)
with col2:
    st.number_input("Prijs (%)", 0, 100, 40, 1, key="price_input", on_change=_sync_from_price)

kwaliteit_pct = st.session_state.quality_input
prijs_pct = st.session_state.price_input
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_pct}%  \n- **Prijs:** {prijs_pct}%")

# --- Puntenschaal ---
st.sidebar.subheader("Puntenschaal")
scales = {
    "0-2-4-6-8-10": [0, 2, 4, 6, 8, 10],
    "0-2,5-5-7,5-10": [0, 2.5, 5, 7.5, 10],
    "0%-20%-40%-60%-80%-100%": [0, 20, 40, 60, 80, 100],
    "0-25-50-75-100": [0, 25, 50, 75, 100],
    "0-30-50-80-100": [0, 30, 50, 80, 100],
    "0-30-50-70": [0, 30, 50, 70],
    "Custom...": None
}
scale_label = st.sidebar.selectbox("Kies een schaal", list(scales.keys()))
if scale_label == "Custom...":
    vals = st.sidebar.text_input("Eigen schaal (komma-gescheiden)", "0,25,50,75,100")
    try:
        scale_values = [float(x) for x in vals.split(",")]
    except:
        st.sidebar.error("Ongeldige schaal (komma-gescheiden getallen).")
        scale_values = [0, 25, 50, 75, 100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

criteria = [c.strip() for c in st.sidebar.text_input("Criterianamen (komma, min 2)", "Kwaliteit,Service").split(",") if c.strip()]
if len(criteria) < 2:
    st.sidebar.error("Voeg minstens 2 criteria toe.")
max_points_criteria = {c: st.sidebar.number_input(f"Max punten {c}", 1, 200, 30) for c in criteria}
max_price_points = st.sidebar.number_input("Max punten Prijs", 1, 200, 40)

st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
verwachte_scores_eigen = {c: float(st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}")) for c in criteria}
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (eigen)", 0.0, 100.0, 10.0, 0.1)
eigen_prijs_points = max_price_points * (1 - margin_pct/100)
st.sidebar.markdown(f"**Eigen Prijsscore (huidig):** {eigen_prijs_points:.1f}")

# --- Scenario invoer concurrenten ---
st.header("📥 Concurrentsituaties")
num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = st.number_input("% duurder dan goedkoopste (conc.)", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}") if not is_cheapest else 0.0
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        # Bewaar ook de marge voor latere herberekeningen
        scenarios.append({"naam": naam, "is_cheapest": is_cheapest, "pct": float(pct), "kval_scores": kval_scores})

# --- Helper functies ---
def score_to_points(s, maxp):
    return (float(s) / float(max_scale)) * float(maxp)

def compute_quality_points(scores_dict):
    return sum(score_to_points(scores_dict[c], max_points_criteria[c]) for c in criteria)

def totals_with_margins(jde_margin, comp_margin, jde_quality_pts, comp_quality_pts):
    """
    Herbereken prijspunten relatief aan de (nieuwe) goedkoopste marge.
    """
    cheapest = min(jde_margin, comp_margin)  # vaak 0, maar kan hoger als beiden > 0
    jde_price_pts = max_price_points * (1 - max(0.0, (jde_margin - cheapest)) / 100.0)
    comp_price_pts = max_price_points * (1 - max(0.0, (comp_margin - cheapest)) / 100.0)
    return (jde_quality_pts + jde_price_pts, comp_quality_pts + comp_price_pts, jde_price_pts, comp_price_pts)

def find_min_margin_for_win(jde_quality_pts, comp_quality_pts, comp_margin, start_margin, step=0.1):
    """
    Zoek de minimale eigen marge (in %-punt) die nodig is om te winnen.
    We verlagen van start_margin naar 0 in stapjes; bij winst geven we target en benodigde daling terug.
    """
    current = start_margin
    best_target = None
    while current > -1e-9:
        my_total, comp_total, _, _ = totals_with_margins(current, comp_margin, jde_quality_pts, comp_quality_pts)
        if my_total > comp_total + 0.005:  # kleine epsilon
            best_target = current
            break
        current = round(current - step, 10)
        if current < 0:
            current = 0.0
    if best_target is not None:
        drop = max(0.0, start_margin - best_target)
        return best_target, drop, True
    # Geen winst haalbaar met prijs alleen (zelfs bij 0%)
    drop = max(0.0, start_margin - 0.0)
    return 0.0, drop, False

def best_one_step_quality_gain(current_scores_dict):
    """
    Vind de beste 1-stap kwaliteitsverbetering (grootste puntenwinst).
    Return: (criterium, current, next, gain) of None
    """
    best = None
    for c in criteria:
        cur = float(current_scores_dict[c])
        higher_steps = [x for x in scale_values if float(x) > cur]
        for nxt in higher_steps:
            gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
            if (best is None) or (gain > best[3]):
                best = (c, cur, float(nxt), float(gain))
    return best

def scenario_scorecard(title, your_quality_pts, your_price_pts, comp_quality_pts, comp_price_pts):
    """
    Horizontale gestapelde balken, dynamische zoom en labels.
    """
    if HAS_MPL:
        total_you = your_quality_pts + your_price_pts
        total_comp = comp_quality_pts + comp_price_pts
        max_total = max(total_you, total_comp)
        min_total = min(total_you, total_comp)
        span = max(5.0, (max_total - min_total) * 1.8)  # vergroot kleine verschillen
        left = max(0.0, min_total - span * 0.10)
        right = max_total + span * 0.10

        fig, ax = plt.subplots(figsize=(7.4, 2.8))
        names = ["Jij", "Concurrent"]
        ax.barh(names, [your_quality_pts, comp_quality_pts], color=QUALITY_COLOR, label="Kwaliteit")
        ax.barh(names, [your_price_pts, comp_price_pts], left=[your_quality_pts, comp_quality_pts], color=PRICE_COLOR, label="Prijs")
        ax.set_xlim(left, right)
        ax.set_xlabel("Punten", color=SECONDARY_BROWN)
        ax.set_title(title, color=PRIMARY_COLOR)

        ax.text(total_you + 0.3, 0, f"{total_you:.1f}", va="center", color=SECONDARY_BROWN, fontsize=10)
        ax.text(total_comp + 0.3, 1, f"{total_comp:.1f}", va="center", color=SECONDARY_BROWN, fontsize=10)

        ax.grid(axis="x", alpha=0.25)
        ax.legend(loc="lower right")
        fig.tight_layout()
        st.pyplot(fig, clear_figure=True)
    else:
        st.caption("Visuele scorekaart (fallback)")
        df_chart = pd.DataFrame({
            "Rol": ["Jij", "Concurrent"],
            "Kwaliteit": [your_quality_pts, comp_quality_pts],
            "Prijs": [your_price_pts, comp_price_pts],
        })
        st.bar_chart(df_chart.set_index("Rol"), height=240)

def dashboard_figure(all_rows):
    """
    Overzicht alle scenario's: per scenario twee horizontale gestapelde balken (Jij vs Concurrent).
    all_rows: list of dicts met keys:
      naam, you_quality, you_price, comp_quality, comp_price, status
    """
    if not HAS_MPL:
        st.info("Dashboard-grafiek vereist matplotlib.")
        return None

    n = len(all_rows)
    height = max(3.5, 0.7 * n)
    fig, ax = plt.subplots(figsize=(10.5, height))

    # Posities: per scenario twee rijen
    y_you = np.arange(n) * 2.0
    y_comp = y_you + 0.8

    names = [r["naam"] for r in all_rows]
    you_q = [r["you_quality"] for r in all_rows]
    you_p = [r["you_price"] for r in all_rows]
    comp_q = [r["comp_quality"] for r in all_rows]
    comp_p = [r["comp_price"] for r in all_rows]
    you_t = [you_q[i] + you_p[i] for i in range(n)]
    comp_t = [comp_q[i] + comp_p[i] for i in range(n)]
    max_total = max(max(you_t), max(comp_t))
    left = 0.0
    right = max_total * 1.20

    # Balken tekenen
    ax.barh(y_you, you_q, color=QUALITY_COLOR, label="Kwaliteit (Jij)")
    ax.barh(y_you, you_p, left=you_q, color=PRICE_COLOR, label="Prijs (Jij)")
    ax.barh(y_comp, comp_q, color="#66BB6A")
    ax.barh(y_comp, comp_p, left=comp_q, color="#42A5F5")

    # Labels en assen
    for i in range(n):
        ax.text(you_t[i] + 0.2, y_you[i], f"{you_t[i]:.1f}", va="center", color=SECONDARY_BROWN, fontsize=9)
        ax.text(comp_t[i] + 0.2, y_comp[i], f"{comp_t[i]:.1f}", va="center", color=SECONDARY_BROWN, fontsize=9)
        ax.text(left + 0.2, y_comp[i], names[i], va="center", ha="left", color=PRIMARY_COLOR, fontweight="bold", fontsize=10)

    ax.set_xlim(left, right)
    ax.set_yticks([])  # we gebruiken tekstlabels
    ax.set_xlabel("Punten", color=SECONDARY_BROWN)
    ax.set_title("Dashboard: overzicht per scenario (Jij vs Concurrent)", color=PRIMARY_COLOR)
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    return fig

def make_pdf(summary_dict, df_overzicht, scenario_details, dashboard_fig=None):
    """
    PDF in JDE-stijl met:
    - Logo
    - Titel + samenvatting
    - Overzichtstabel
    - Actiepunten per verlies-situatie
    - Optioneel dashboard-figuur (PNG embed)
    """
    if not HAS_RL:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name="JDETitle", parent=styles["Title"], textColor=colors.HexColor(PRIMARY_COLOR), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="JDEHeading2", parent=styles["Heading2"], textColor=colors.HexColor(PRIMARY_COLOR), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="JDEHeading3", parent=styles["Heading3"], textColor=colors.HexColor(SECONDARY_BROWN)))
    styles.add(ParagraphStyle(name="JDENormal", parent=styles["Normal"], textColor=colors.black))

    flow = []
    if os.path.exists(LOGO_PATH):
        flow.append(Image(LOGO_PATH, width=100, height=48))
        flow.append(Spacer(1, 6))

    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["JDETitle"]))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(summary_dict["headline"], styles["JDENormal"]))
    flow.append(Spacer(1, 14))

    table_data = [["Scenario", "Status", "Jouw punten", "Concurrent", "Prijsactie (%-punt)", "Kwaliteitsadvies"]]
    for idx, row in df_overzicht.reset_index().iterrows():
        table_data.append([
            str(row["Scenario"]),
            str(row["Status"]),
            f"{row['JDE (totaal)']}",
            f"{row['Concurrent (totaal)']}",
            str(row.get("Prijsactie (%-punt)", "")),
            str(row.get("Kwaliteitsadvies (1 stap)", "")),
        ])
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor(SECONDARY_BROWN)),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F2EA")]),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 16))

    if scenario_details:
        flow.append(Paragraph("Concrete acties bij verlies-situaties", styles["JDEHeading2"]))
        flow.append(Spacer(1, 8))
        for d in scenario_details:
            flow.append(Paragraph(f"<b>{d['naam']}</b> — {d['gap_text']}", styles["JDEHeading3"]))
            for p in d["bullets"]:
                flow.append(Paragraph(f"• {p}", styles["JDENormal"]))
            flow.append(Spacer(1, 8))

    if dashboard_fig is not None and HAS_MPL:
        img_buf = io.BytesIO()
        dashboard_fig.savefig(img_buf, format="png", dpi=160, bbox_inches="tight")
        img_buf.seek(0)
        flow.append(Spacer(1, 12))
        flow.append(Paragraph("Dashboard-overzicht", styles["JDEHeading2"]))
        flow.append(Spacer(1, 6))
        flow.append(Image(ImageReader(img_buf), width=480, height=280))

    doc.build(flow)
    buf.seek(0)
    return buf.getvalue()

# --- Analyse & Resultaten ---
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # Eigen kwaliteitspunten
    jde_quality_pts = compute_quality_points(verwachte_scores_eigen)
    # Huidige prijspunten (alleen informatief; voor berekening gebruiken we relatieve herrekening per scenario)
    jde_price_pts_current = max_price_points * (1 - margin_pct/100)
    jde_total_current = jde_quality_pts + jde_price_pts_current

    overzicht_rows = []
    scenario_advices = []

    # Counters voor sales-samenvatting
    wins_no_action = 0
    wins_via_price = 0
    wins_via_quality = 0
    wins_via_combo = 0
    not_feasible = 0

    # Voor dashboard
    dashboard_rows = []

    st.subheader("Samenvatting per situatie (mensentaal)")
    for s in scenarios:
        comp_quality_pts = compute_quality_points(s["kval_scores"])
        comp_margin = 0.0 if s["is_cheapest"] else float(s["pct"])

        # Huidige totals bij huidige marges (relatief aan huidige goedkoopste)
        my_total_now, comp_total_now, my_price_now, comp_price_now = totals_with_margins(
            margin_pct, comp_margin, jde_quality_pts, comp_quality_pts
        )

        # Status nu
        if my_total_now > comp_total_now + 1e-9:
            status, icon = "WIN", "✅"
        elif my_total_now + 1e-9 < comp_total_now:
            status, icon = "LOSE", "❌"
        else:
            status, icon = "DRAW", "⚠️"

        st.markdown(f"### {icon} {s['naam']} — {status}")
        st.write(f"**Jouw totaalscore (nu):** {my_total_now:.1f}  |  **Concurrent (nu):** {comp_total_now:.1f}")

        # Visuele scorekaart
        with st.expander("Toon visuele scorekaart"):
            scenario_scorecard(
                s['naam'],
                jde_quality_pts, my_price_now,
                comp_quality_pts, comp_price_now
            )

        # Actieroutes
        qual_hint = ""
        price_drop_txt = ""

        if status == "WIN":
            wins_no_action += 1
            st.success("Je wint zonder actie. Vasthouden.")
        else:
            # Prijs-route: zoek minimale eigen marge voor WIN
            target_margin, drop_win, feasible_price_win = find_min_margin_for_win(
                jde_quality_pts, comp_quality_pts, comp_margin, margin_pct, step=0.1
            )
            if drop_win > 0:
                if feasible_price_win:
                    st.warning(
                        f"**Prijs-route (WIN):** verlaag je prijs met **{drop_win:.1f} %-punt** "
                        f"(naar {target_margin:.1f}% boven goedkoopste)."
                    )
                    wins_via_price += 1
                    price_drop_txt = f"{drop_win:.1f} (naar {target_margin:.1f}%)"
                else:
                    st.info(
                        "Zelfs als je de goedkoopste bent (0% marge), is prijs alléén onvoldoende voor winst. "
                        "Combineer met een kwaliteitsstap."
                    )

            # Kwaliteit-route (één stap) – bereken gap bij huidige marges
            gap = (comp_total_now - my_total_now)
            suggestion = None
            for c in criteria:
                cur = float(verwachte_scores_eigen[c])
                higher_steps = [n for n in scale_values if float(n) > cur]
                for nxt in higher_steps:
                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                    # Check winst met alleen kwaliteit (bij huidige marges)
                    my_total_with_quality = my_total_now + gain
                    if my_total_with_quality > comp_total_now + 0.005:
                        suggestion = (c, cur, float(nxt), float(gain))
                        break
                if suggestion:
                    break

            if suggestion:
                c, cur, nxt, gain = suggestion
                st.info(f"**Kwaliteit-route (1 stap):** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) voor winst.")
                qual_hint = f"{c}: {cur}→{nxt}"
                wins_via_quality += 1
            else:
                # Combi-route: beste 1-stap + minimale prijsdaling voor WIN
                best_step = best_one_step_quality_gain(verwachte_scores_eigen)
                if best_step:
                    c, cur, nxt, gain = best_step
                    # Simuleer met nieuwe kwaliteit
                    new_jde_quality = jde_quality_pts + gain
                    target_margin2, drop_win2, feasible_price_win2 = find_min_margin_for_win(
                        new_jde_quality, comp_quality_pts, comp_margin, margin_pct, step=0.1
                    )
                    if drop_win2 > 0 and feasible_price_win2:
                        st.info(
                            f"**Combi-route:** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) "
                            f"én verlaag prijs met **{drop_win2:.1f} %-punt** (naar {target_margin2:.1f}%)."
                        )
                        qual_hint = f"{c}: {cur}→{nxt}"
                        price_drop_txt = f"{drop_win2:.1f} (naar {target_margin2:.1f}%)"
                        wins_via_combo += 1
                    else:
                        st.info("Zelfs met beste één-stap kwaliteit is een flinke prijsdaling nodig; heroverweeg criteria of positionering.")
                        not_feasible += 1
                else:
                    st.info("Geen zinvolle één-stap kwaliteitsverbetering beschikbaar.")
                    not_feasible += 1

        # Overzicht rij
        overzicht_rows.append({
            "Scenario": s["naam"],
            "JDE (totaal)": round(my_total_now, 1),
            "Concurrent (totaal)": round(comp_total_now, 1),
            "Status": status,
            "Prijsactie (%-punt)": price_drop_txt,
            "Kwaliteitsadvies (1 stap)": qual_hint,
        })

        # Dashboard row (gebruik huidige marges)
        dashboard_rows.append({
            "naam": s["naam"],
            "you_quality": jde_quality_pts,
            "you_price": my_price_now,
            "comp_quality": comp_quality_pts,
            "comp_price": comp_price_now,
            "status": status
        })

    # Overzicht
    df_overzicht = pd.DataFrame(overzicht_rows).set_index("Scenario")
    st.subheader("Overzicht alle scenario's")
    st.dataframe(df_overzicht, use_container_width=True)

    # Dashboard-grafiek
    st.subheader("📊 Dashboard-grafiek (alle scenario's)")
    dash_fig = dashboard_figure(dashboard_rows)

    # Salesvriendelijke samenvatting
    total = len(scenarios)
    st.subheader("🧭 Samenvatting (actiegericht)")
    st.markdown(f"""
**Zonder actie WIN:** {wins_no_action}/{total}  
**WIN via prijs:** {wins_via_price}  
**WIN via één kwaliteitsstap:** {wins_via_quality}  
**WIN via combinatie (stap + prijs):** {wins_via_combo}  
**Niet haalbaar met simpele acties:** {not_feasible}  
""")
    st.caption("Voorkom verlies door vooraf prijsruimte te creëren in ‘combi’ en ‘niet haalbaar’-cases, of versterk inhoudelijk het zwakste criterium.")

    # Downloads
    csv = df_overzicht.to_csv(index=True)
    st.download_button("Download overzicht (CSV)", data=csv, file_name="winkans_overzicht.csv", mime="text/csv")

    summary_dict = {
        "headline": (
            f"JDE-stijl advies • WIN zonder actie: {wins_no_action}/{total} • "
            f"Prijs-route WIN: {wins_via_price} • Kwaliteit-route WIN: {wins_via_quality} • "
            f"Combi-route WIN: {wins_via_combo} • Niet haalbaar: {not_feasible} • "
            f"Kwaliteit%: {kwaliteit_pct}% • Prijs%: {prijs_pct}%"
        )
    }
    pdf_bytes = make_pdf(summary_dict, df_overzicht, scenario_advices=[], dashboard_fig=dash_fig)

    if pdf_bytes:
        st.download_button("📄 Download printbare adviespagina (PDF)", data=pdf_bytes, file_name="advies_winkans_bpkv.pdf", mime="application/pdf")
    else:
        st.info("PDF niet beschikbaar (reportlab ontbreekt). Voeg 'reportlab' toe aan requirements.txt of redeploy.")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
