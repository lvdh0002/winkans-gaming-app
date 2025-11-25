streamlit>=1.31
pandas
numpy
matplotlib
reportlab

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
st.title("Tool om winkansen te berekenen o.b.v. de BPKV-methode (Beste Prijs Kwaliteit Verhouding)")

# --- JDE Professional Huisstijl (geïnspireerd op JDE Pro look & feel: rood/bruin/beige) ---
PRIMARY_COLOR = "#8B0000"   # Diep rood
SECONDARY_BROWN = "#5A3A29" # Koffiebruin
ACCENT_BEIGE = "#E8D7C1"    # Beige
ACCENT_GOLD  = "#C0A060"    # Goudaccent

QUALITY_COLOR = "#4CAF50"   # Groen voor kwaliteit (duidelijk contrast)
PRICE_COLOR   = "#2196F3"   # Blauw voor prijs (duidelijk contrast)

LOGO_PATH = os.path.join("assets", "logo_jde.png")

# App-brede CSS in JDE-stijl
JDE_CSS = f"""
<style>
/* Achtergrond en fonts */
html, body, .stApp {{
  background-color: #FAF7F2;
  font-family: Arial, Helvetica, sans-serif;
}}
/* Koppen */
h1, h2, h3, h4 {{
  color: {PRIMARY_COLOR};
}}
/* Buttons */
.stButton>button {{
  background-color: {PRIMARY_COLOR};
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.6rem 1rem;
}}
.stButton>button:hover {{
  background-color: {SECONDARY_BROWN};
  color: #fff;
}}
/* Expander */
.streamlit-expanderHeader {{
  color: {SECONDARY_BROWN};
  font-weight: 600;
}}
/* Tabellen */
thead tr th {{
  background-color: {ACCENT_BEIGE} !important;
  color: {SECONDARY_BROWN} !important;
}}
/* Sidebar accenten */
.css-1d391kg, .stSidebar > div:first-child {{
  background-color: #FCF9F5;
}}
</style>
"""
st.markdown(JDE_CSS, unsafe_allow_html=True)

# Logo tonen
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=140)

# --- Stap 1: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")

def _sync_from_quality() -> None:
    st.session_state.price_input = 100 - st.session_state.quality_input

def _sync_from_price() -> None:
    st.session_state.quality_input = 100 - st.session_state.price_input

col1, col2 = st.sidebar.columns(2)
with col1:
    st.number_input(
        "Kwaliteit (%)",
        min_value=0,
        max_value=100,
        value=60,
        step=1,
        help="Vul kwaliteit in; prijs wordt automatisch 100 - kwaliteit",
        key="quality_input",
        on_change=_sync_from_quality,
    )
with col2:
    st.number_input(
        "Prijs (%)",
        min_value=0,
        max_value=100,
        value=40,
        step=1,
        help="Vul prijs in; kwaliteit wordt automatisch 100 - prijs",
        key="price_input",
        on_change=_sync_from_price,
    )

kwaliteit_pct = st.session_state.quality_input
prijs_pct = st.session_state.price_input
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_pct}%  \n- **Prijs:** {prijs_pct}%")

# --- Puntenschaal selectie ---
st.sidebar.subheader("Puntenschaal voor beoordeling")
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
        st.sidebar.error("Ongeldige schaal, gebruik getallen gescheiden door komma.")
        scale_values = [0, 25, 50, 75, 100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

criteria = st.sidebar.text_input("Criterianamen (komma, min 2)", "Kwaliteit,Service").split(",")
criteria = [c.strip() for c in criteria if c.strip()]
max_points_criteria = {}
for c in criteria:
    max_points_criteria[c] = st.sidebar.number_input(f"Max punten {c}", min_value=1, value=60, step=1)

max_price_points = st.sidebar.number_input("Max punten Prijs", min_value=1, value=40, step=1)
st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
verwachte_scores_eigen = {}
for c in criteria:
    score = st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}")
    verwachte_scores_eigen[c] = float(score)
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste", 0.0, 100.0, 10.0, 0.1)
eigen_prijs_points = max_price_points * (1 - margin_pct / 100)
st.sidebar.markdown(f"**Eigen Prijsscore:** {eigen_prijs_points:.1f}")

# --- Scenario invoer concurrenten ---
st.header("📥 Concurrentsituaties (max 15)")
num_scen = st.number_input("Aantal situaties", 1, 15, 3, 1)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = st.number_input("% duurder dan goedkoopste", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}") if not is_cheapest else 0.0
        prijs_pts = max_price_points * (1.0 if is_cheapest else (1.0 - float(pct) / 100.0))
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam": naam, "prijs_pts": prijs_pts, "kval_scores": kval_scores})

# --- Helper functies ---
def score_to_points(s, maxp, max_scale):
    return (float(s) / float(max_scale)) * float(maxp)

def price_route_for_win(comp_total, your_quality_pts, max_price_points, current_margin_pct):
    """
    Winst-focus: hoeveel %-punt moet je prijs zakken om de concurrent te overtreffen?
    Return: (target_margin_pct, drop_pct, feasible_bool)
    """
    required_price_points = (comp_total + 0.01) - your_quality_pts
    if required_price_points > max_price_points:
        # zelfs als je 0% marge (goedkoopste) hebt, is winnen niet haalbaar via prijs alleen
        return 0.0, current_margin_pct, False
    target_margin_pct = 100.0 * (1.0 - required_price_points / max_price_points)
    target_margin_pct = float(np.clip(target_margin_pct, 0.0, 100.0))
    drop_pct = current_margin_pct - target_margin_pct
    return target_margin_pct, drop_pct, True

def best_one_step_quality_gain(criteria, scale_values, current_scores_dict, max_points_criteria, max_scale):
    """
    Vind de beste 1-stap kwaliteitsverbetering (grootste puntenwinst).
    Return: (criterium, current, next, gain) of None
    """
    best = None
    for c in criteria:
        cur = float(current_scores_dict[c])
        higher_steps = [x for x in scale_values if float(x) > cur]
        for nxt in higher_steps:
            gain = score_to_points(nxt, max_points_criteria[c], max_scale) - score_to_points(cur, max_points_criteria[c], max_scale)
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
        # Zoom: toon alleen relevante range met marge
        span = max(5.0, (max_total - min_total) * 1.5)  # vergroot kleine verschillen
        left = max(0.0, min_total - span * 0.10)
        right = max_total + span * 0.10

        fig, ax = plt.subplots(figsize=(7.2, 2.8))
        names = ["Jij", "Concurrent"]
        # balken
        ax.barh(names, [your_quality_pts, comp_quality_pts], color=QUALITY_COLOR, label="Kwaliteit")
        ax.barh(names, [your_price_pts, comp_price_pts], left=[your_quality_pts, comp_quality_pts], color=PRICE_COLOR, label="Prijs")
        ax.set_xlim(left, right)
        ax.set_xlabel("Punten")
        ax.set_title(title, color=PRIMARY_COLOR)

        # labels (totaal)
        ax.text(total_you + 0.2, 0, f"{total_you:.1f}", va="center", color=SECONDARY_BROWN)
        ax.text(total_comp + 0.2, 1, f"{total_comp:.1f}", va="center", color=SECONDARY_BROWN)

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
        st.info("Dashboard-grafiek vereist matplotlib. Voeg 'matplotlib' toe aan requirements.txt.")
        return

    n = len(all_rows)
    height = max(3.5, 0.7 * n)
    fig, ax = plt.subplots(figsize=(9.5, height))

    # Posities: per scenario twee rijen
    y_positions_you = np.arange(n) * 2.0
    y_positions_comp = y_positions_you + 0.8

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
    ax.barh(y_positions_you, you_q, color=QUALITY_COLOR, label="Kwaliteit (Jij)")
    ax.barh(y_positions_you, you_p, left=you_q, color=PRICE_COLOR, label="Prijs (Jij)")
    ax.barh(y_positions_comp, comp_q, color="#81C784")        # lichtere groen voor onderscheid
    ax.barh(y_positions_comp, comp_p, left=comp_q, color="#64B5F6")

    # Labels en assen
    for i in range(n):
        ax.text(you_t[i] + 0.2, y_positions_you[i], f"{you_t[i]:.1f}", va="center", color=SECONDARY_BROWN)
        ax.text(comp_t[i] + 0.2, y_positions_comp[i], f"{comp_t[i]:.1f}", va="center", color=SECONDARY_BROWN)
        # Scenario-namen links
        ax.text(left + 0.2, y_positions_comp[i], names[i], va="center", ha="left", color=PRIMARY_COLOR, fontweight="bold")

    ax.set_xlim(left, right)
    ax.set_yticks([])  # we gebruiken tekstlabels
    ax.set_xlabel("Punten")
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

    # Custom paragrafen in JDE-kleur
    styles.add(ParagraphStyle(name="JDETitle", parent=styles["Title"], textColor=colors.HexColor(PRIMARY_COLOR)))
    styles.add(ParagraphStyle(name="JDEHeading2", parent=styles["Heading2"], textColor=colors.HexColor(PRIMARY_COLOR)))
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

    # Overzichtstabel
    table_data = [["Scenario", "Status", "Jouw punten", "Concurrent", "Prijsactie (%-punt)", "Kwaliteitsadvies"]]
    for idx, row in df_overzicht.reset_index().iterrows():
        table_data.append([
            str(row["Scenario"]),
            str(row["Status"]),
            f"{row['JDE (totaal)']}",
            f"{row['Concurrent (totaal)']}",
            str(row.get("Prijs: zak %-punt", "")),
            str(row["Kwaliteitsadvies (1 stap)"]),
        ])
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(ACCENT_BEIGE)),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor(SECONDARY_BROWN)),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor(SECONDARY_BROWN)),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F2EA")]),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 16))

    # Scenario-acties
    if scenario_details:
        flow.append(Paragraph("Concrete acties bij verlies-situaties", styles["JDEHeading2"]))
        flow.append(Spacer(1, 8))
        for d in scenario_details:
            flow.append(Paragraph(f"<b>{d['naam']}</b> — {d['gap_text']}", styles["JDEHeading3"]))
            for p in d["bullets"]:
                flow.append(Paragraph(f"• {p}", styles["JDENormal"]))
            flow.append(Spacer(1, 8))

    # Dashboard-figuur (optioneel)
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
    # Jouw punten
    jde_quality_pts = sum(score_to_points(verwachte_scores_eigen[c], max_points_criteria[c], max_scale) for c in criteria)
    jde_price_pts = eigen_prijs_points
    jde_total = jde_quality_pts + jde_price_pts

    overzicht_rows = []
    scenario_advices = []

    # counters voor samenvatting
    wins_no_action = 0
    wins_via_price = 0
    wins_via_quality = 0
    wins_via_combo = 0
    not_feasible = 0

    # Voor dashboard
    dashboard_rows = []

    st.subheader("Samenvatting per situatie (mensentaal)")
    for s in scenarios:
        comp_quality_pts = sum(score_to_points(s['kval_scores'][c], max_points_criteria[c], max_scale) for c in criteria)
        comp_price_pts = s['prijs_pts']
        comp_total = comp_quality_pts + comp_price_pts

        # Status
        if jde_total > comp_total:
            status, icon = "WIN", "✅"
        elif jde_total < comp_total:
            status, icon = "LOSE", "❌"
        else:
            status, icon = "DRAW", "⚠️"

        st.markdown(f"### {icon} {s['naam']} — {status}")
        st.write(f"**Jouw totaalscore:** {jde_total:.1f}  |  **Concurrent:** {comp_total:.1f}")

        # Visuele scorekaart
        with st.expander("Toon visuele scorekaart"):
            scenario_scorecard(
                s['naam'],
                jde_quality_pts, jde_price_pts,
                comp_quality_pts, comp_price_pts
            )

        qual_hint = ""
        max_over_pct_txt = ""
        price_drop_txt = ""

        if status == "WIN":
            wins_no_action += 1
            st.success("Je wint. Je huidige combinatie van kwaliteit en prijs is voldoende. Blijf dit niveau vasthouden.")
        elif status == "DRAW":
            # Met kleine actie kun je winnen; bereken directe prijsroute
            target_margin_pct, drop_win, feasible = price_route_for_win(comp_total, jde_quality_pts, max_price_points, margin_pct)
            if feasible and drop_win > 0:
                st.warning(f"**Prijs-route (winst):** verlaag je prijs met **{drop_win:.1f} %-punt** (van {margin_pct:.1f}% naar {target_margin_pct:.1f}%).")
                wins_via_price += 1
                price_drop_txt = f"{drop_win:.1f} (naar {target_margin_pct:.1f}%)"
                max_over_pct_txt = f"{target_margin_pct:.1f}%"
            else:
                # Kwaliteit-route (1 stap)
                gap = (comp_total - jde_total) + 0.01
                suggestion = None
                for c in criteria:
                    current = float(verwachte_scores_eigen[c])
                    higher_steps = [n for n in scale_values if float(n) > current]
                    for nxt in higher_steps:
                        gain = score_to_points(nxt, max_points_criteria[c], max_scale) - score_to_points(current, max_points_criteria[c], max_scale)
                        if gain >= gap:
                            suggestion = (c, current, float(nxt), float(gain))
                            break
                    if suggestion:
                        break
                if suggestion:
                    c, cur, nxt, gain = suggestion
                    st.info(f"**Kwaliteit-route (1 stap):** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) om te winnen.")
                    qual_hint = f"{c}: {cur}→{nxt}"
                    wins_via_quality += 1
                else:
                    # Combi
                    best_step = best_one_step_quality_gain(criteria, scale_values, verwachte_scores_eigen, max_points_criteria, max_scale)
                    if best_step:
                        c, cur, nxt, gain = best_step
                        new_quality_pts = jde_quality_pts + gain
                        target_margin_pct2, drop_win2, feasible2 = price_route_for_win(comp_total, new_quality_pts, max_price_points, margin_pct)
                        if feasible2:
                            st.info(
                                f"**Combi-route:** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) "
                                f"én verlaag prijs met **{drop_win2:.1f} %-punt** (naar {target_margin_pct2:.1f}%) om te winnen."
                            )
                            qual_hint = f"{c}: {cur}→{nxt}"
                            price_drop_txt = f"{drop_win2:.1f} (naar {target_margin_pct2:.1f}%)"
                            max_over_pct_txt = f"{target_margin_pct2:.1f}%"
                            wins_via_combo += 1
                        else:
                            st.info("Zelfs met beste één-stap kwaliteitsverbetering is winnen via combinatie niet haalbaar. Overweeg grotere kwaliteitsstap of prijsstrategie.")
                            not_feasible += 1
                    else:
                        st.info("Geen zinvolle één-stap kwaliteitsverbetering beschikbaar.")
                        not_feasible += 1

        else:  # LOSE
            gap = comp_total - jde_total
            # Directe prijsroute voor WIN
            target_margin_pct, drop_win, feasible = price_route_for_win(comp_total, jde_quality_pts, max_price_points, margin_pct)
            if feasible and drop_win > 0:
                st.warning(f"**Prijs-route (winst):** verlaag je prijs met **{drop_win:.1f} %-punt** (van {margin_pct:.1f}% naar {target_margin_pct:.1f}%).")
                wins_via_price += 1
                price_drop_txt = f"{drop_win:.1f} (naar {target_margin_pct:.1f}%)"
                max_over_pct_txt = f"{target_margin_pct:.1f}%"
            elif feasible and drop_win <= 0:
                st.info("**Prijs-route:** je hebt al voldoende prijspunten voor winst; focus op kleine kwaliteitsverbetering.")
            else:
                st.info("**Prijs-route (alleen prijs):** niet haalbaar (zelfs als je de goedkoopste bent). Kijk naar kwaliteit of combinatie.")

            # Kwaliteit-route (1 stap)
            suggestion = None
            for c in criteria:
                current = float(verwachte_scores_eigen[c])
                higher_steps = [n for n in scale_values if float(n) > current]
                for nxt in higher_steps:
                    gain = score_to_points(nxt, max_points_criteria[c], max_scale) - score_to_points(current, max_points_criteria[c], max_scale)
                    if gain >= (gap + 0.01):  # winmarge
                        suggestion = (c, current, float(nxt), float(gain))
                        break
                if suggestion:
                    break
            if suggestion:
                c, cur, nxt, gain = suggestion
                st.info(f"**Kwaliteit-route (1 stap):** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) om te winnen.")
                qual_hint = f"{c}: {cur}→{nxt}"
                wins_via_quality += 1
            else:
                # Combi-route: beste 1-stap + prijsdaling
                best_step = best_one_step_quality_gain(criteria, scale_values, verwachte_scores_eigen, max_points_criteria, max_scale)
                if best_step:
                    c, cur, nxt, gain = best_step
                    new_quality_pts = jde_quality_pts + gain
                    target_margin_pct2, drop_win2, feasible2 = price_route_for_win(comp_total, new_quality_pts, max_price_points, margin_pct)
                    if feasible2 and drop_win2 > 0:
                        st.info(
                            f"**Combi-route:** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) "
                            f"én verlaag prijs met **{drop_win2:.1f} %-punt** (naar {target_margin_pct2:.1f}%) om te winnen."
                        )
                        qual_hint = f"{c}: {cur}→{nxt}"
                        price_drop_txt = f"{drop_win2:.1f} (naar {target_margin_pct2:.1f}%)"
                        max_over_pct_txt = f"{target_margin_pct2:.1f}%"
                        wins_via_combo += 1
                    else:
                        st.info("**Combi-route:** zelfs met beste één-stap kwaliteit is prijsdaling niet voldoende/zinvol. Overweeg grotere kwaliteitsstap of inhoudelijke herpositionering.")
                        not_feasible += 1
                else:
                    st.info("**Kwaliteit-route:** geen zinvolle één-stap verbetering mogelijk.")
                    not_feasible += 1

        # Overzicht rij
        overzicht_rows.append({
            "Scenario": s["naam"],
            "JDE (totaal)": round(jde_total, 1),
            "Concurrent (totaal)": round(comp_total, 1),
            "Status": status,
            "Max % duurder (voor winst)": max_over_pct_txt,
            "Prijs: zak %-punt": price_drop_txt,
            "Kwaliteitsadvies (1 stap)": qual_hint,
        })

        # Dashboard row
        dashboard_rows.append({
            "naam": s["naam"],
            "you_quality": jde_quality_pts,
            "you_price": jde_price_pts,
            "comp_quality": comp_quality_pts,
            "comp_price": comp_price_pts,
            "status": status
        })

    # Overzichtstabel
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
- **Zonder actie win je in:** **{wins_no_action} van {total}** scenario's.  
- **Via prijs alleen (winst):** **{wins_via_price}** scenario's.  
- **Via één kwaliteitsstap:** **{wins_via_quality}** scenario's.  
- **Combinatie (kleine prijsdaling + 1 kwaliteitsstap):** **{wins_via_combo}** scenario's.  
- **Niet haalbaar met simpele acties:** **{not_feasible}** scenario's.  
    """)
    st.caption("Tip: voorkom verlies door in de ‘combi’ en ‘niet haalbaar’-cases vooraf prijsruimte te creëren of inhoudelijk te versterken op de zwakste criteria.")

    # Downloads
    csv = df_overzicht.to_csv(index=True)
    st.download_button("Download overzicht (CSV)", data=csv, file_name="winkans_overzicht.csv", mime="text/csv")

    summary_dict = {
        "headline": (
            f"JDE-stijl advies • Zonder actie WIN: {wins_no_action}/{total} • "
            f"Prijs-route WIN: {wins_via_price} • Kwaliteit-route WIN: {wins_via_quality} • "
            f"Combi-route WIN: {wins_via_combo} • Niet haalbaar: {not_feasible} • "
            f"Kwaliteit%: {kwaliteit_pct}% • Prijs%: {prijs_pct}%"
        )
    }
    pdf_bytes = make_pdf(summary_dict, df_overzicht, scenario_advices=[], dashboard_fig=dash_fig)

    if pdf_bytes:
        st.download_button("📄 Download printbare adviespagina (PDF)", data=pdf_bytes, file_name="advies_winkans_bpkv.pdf", mime="application/pdf")
    else:
        # Fallback: markdown advies
        md = []
        md.append("# Advies: Winkans & Acties (BPKV)\n")
        md.append(summary_dict["headline"])
        md.append("\n## Overzicht\n")
        md.append(df_overzicht.to_markdown())
        md_text = "\n".join(md)
        st.download_button("📝 Download advies (Markdown)", data=md_text.encode("utf-8"), file_name="advies_winkans_bpkv.md", mime="text/markdown")

else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
