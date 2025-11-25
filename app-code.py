import streamlit as st
import pandas as pd
import numpy as np
import io
import os

# --- Robust imports ---
HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except Exception:
    HAS_MPL = False

HAS_RL = True
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except Exception:
    HAS_RL = False

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
st.title("Tool om winkansen te berekenen o.b.v. de BPKV-methode (Beste Prijs Kwaliteit Verhouding)")

# --- JDE Huisstijl ---
PRIMARY_COLOR = "#8B0000"
ACCENT_COLOR = "#C0A060"
QUALITY_COLOR = "#4CAF50"
PRICE_COLOR = "#2196F3"
LOGO_PATH = os.path.join("assets", "logo_jde.png")

if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=120)

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
        pct = st.number_input("% duurder dan goedkoopste", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}") if not is_cheapest else 0
        prijs_pts = max_price_points * (1 if is_cheapest else 1 - pct / 100)
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam": naam, "prijs_pts": prijs_pts, "kval_scores": kval_scores})

# --- Helper functies ---
def score_to_points(s, maxp, max_scale):
    return (float(s) / float(max_scale)) * float(maxp)

def compute_price_route_for_draw(comp_total, your_quality_pts, max_price_points, current_margin_pct):
    required_price_points = comp_total - your_quality_pts
    margin_required_pct = 100.0 * (1.0 - required_price_points / max_price_points)
    margin_required_pct = float(np.clip(margin_required_pct, 0.0, 100.0))
    drop_pct = current_margin_pct - margin_required_pct
    return margin_required_pct, drop_pct

def compute_price_route_for_win(comp_total, your_quality_pts, max_price_points, current_margin_pct):
    required_price_points = (comp_total + 0.01) - your_quality_pts
    margin_required_pct = 100.0 * (1.0 - required_price_points / max_price_points)
    margin_required_pct = float(np.clip(margin_required_pct, 0.0, 100.0))
    drop_pct = current_margin_pct - margin_required_pct
    return margin_required_pct, drop_pct

def scenario_scorecard(title, your_quality_pts, your_price_pts, comp_quality_pts, comp_price_pts):
    if HAS_MPL:
        fig, ax = plt.subplots(figsize=(5.2, 3.4))
        names = ["Jij", "Concurrent"]
        quality = [your_quality_pts, comp_quality_pts]
        price = [your_price_pts, comp_price_pts]
        ax.bar(names, quality, label="Kwaliteit", color=QUALITY_COLOR)
        ax.bar(names, price, bottom=quality, label="Prijs", color=PRICE_COLOR)
        ax.set_title(title, color=PRIMARY_COLOR)
        ax.set_ylabel("Punten")
        ax.legend(loc="upper right")
        ax.set_ylim(0, max(your_quality_pts + your_price_pts, comp_quality_pts + comp_price_pts) * 1.15)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        st.pyplot(fig, clear_figure=True)
    else:
        st.caption("Visuele scorekaart (fallback)")
        df_chart = pd.DataFrame({
            "Rol": ["Jij", "Jij", "Concurrent", "Concurrent"],
            "Type": ["Kwaliteit", "Prijs", "Kwaliteit", "Prijs"],
            "Punten": [your_quality_pts, your_price_pts, comp_quality_pts, comp_price_pts]
        })
        pivot = df_chart.pivot_table(index="Rol", columns="Type", values="Punten", aggfunc="sum").fillna(0)
        st.bar_chart(pivot, height=240)

def make_pdf(summary_dict, df_overzicht, scenario_details):
    if not HAS_RL:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    flow = []
    if os.path.exists(LOGO_PATH):
        flow.append(Image(LOGO_PATH, width=80, height=40))
    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["Title"]))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(summary_dict["headline"], styles["Normal"]))
    flow.append(Spacer(1, 12))

    # Overzichtstabel
    table_data = [["Scenario", "Status", "Jouw punten", "Concurrent", "Max % duurder", "Kwaliteitsadvies"]]
    for idx, row in df_overzicht.reset_index().iterrows():
        table_data.append([
            str(row["Scenario"]),
            str(row["Status"]),
            f"{row['JDE (totaal)']}",
            f"{row['Concurrent (totaal)']}",
            str(row["Max % duurder (gelijkspel)"]),
            str(row["Kwaliteitsadvies (1 stap)"]),
        ])
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 16))

    # Scenario adviezen
    if scenario_details:
        flow.append(Paragraph("Concrete acties bij verlies-situaties", styles["Heading2"]))
        flow.append(Spacer(1, 8))
        for d in scenario_details:
            flow.append(Paragraph(f"<b>{d['naam']}</b> — {d['gap_text']}", styles["Heading3"]))
            for p in d["bullets"]:
                flow.append(Paragraph(f"• {p}", styles["Normal"]))
            flow.append(Spacer(1, 8))

    doc.build(flow)
    buf.seek(0)
   # --- Analyse & Resultaten ---
st.header("Resultaten")

if st.button("Bereken winkansen"):
    jde_quality_pts = sum(score_to_points(verwachte_scores_eigen[c], max_points_criteria[c], max_scale) for c in criteria)
    jde_price_pts = eigen_prijs_points
    jde_total = jde_quality_pts + jde_price_pts
    overzicht_rows = []
    scenario_advices = []
    wins = draws = losses = 0
    price_easy = quality_easy = 0

    for s in scenarios:
        comp_quality_pts = sum(score_to_points(s['kval_scores'][c], max_points_criteria[c], max_scale) for c in criteria)
        comp_price_pts = s['prijs_pts']
        comp_total = comp_quality_pts + comp_price_pts
        status = "WIN" if jde_total > comp_total else "LOSE" if jde_total < comp_total else "DRAW"
        icon = "✅" if status == "WIN" else "❌" if status == "LOSE" else "⚠️"
        if status == "WIN": wins += 1
        elif status == "DRAW": draws += 1
        else: losses += 1

        st.markdown(f"### {icon} {s['naam']} — {status}")
        st.write(f"**Jouw totaalscore:** {jde_total:.1f} | **Concurrent:** {comp_total:.1f}")
        with st.expander("Toon visuele scorekaart"):
            scenario_scorecard(s['naam'], jde_quality_pts, jde_price_pts, comp_quality_pts, comp_price_pts)

        qual_hint = ""
        max_over_pct_txt = ""
        if status == "LOSE":
            gap = comp_total - jde_total
            margin_req_draw, drop_draw = compute_price_route_for_draw(comp_total, jde_quality_pts, max_price_points, margin_pct)
            margin_req_win, drop_win = compute_price_route_for_win(comp_total, jde_quality_pts, max_price_points, margin_pct)
            if drop_draw > 0:
                st.warning(f"**Prijs-route (gelijkspel):** verlaag met **{drop_draw:.1f} %-punt** (van {margin_pct:.1f}% naar {margin_req_draw:.1f}%).")
                price_easy += 1
                max_over_pct_txt = f"{margin_req_draw:.1f}%"
            if drop_win > 0:
                st.warning(f"**Prijs-route (winst):** verlaag met **{drop_win:.1f} %-punt** (van {margin_pct:.1f}% naar {margin_req_win:.1f}%).")

            suggestion = None
            for c in criteria:
                current = float(verwachte_scores_eigen[c])
                for nxt in [n for n in scale_values if n > current]:
                    gain = score_to_points(nxt, max_points_criteria[c], max_scale) - score_to_points(current, max_points_criteria[c], max_scale)
                    if gain >= gap + 0.01:
                        suggestion = (c, current, nxt, gain)
                        break
                if suggestion: break
            if suggestion:
                c, cur, nxt, gain = suggestion
                st.info(f"**Kwaliteit-route:** verhoog **{c}** van {cur} naar {nxt} (+{gain:.1f} ptn) om te winnen.")
                qual_hint = f"{c}: {cur}→{nxt}"
                quality_easy += 1

            scenario_advices.append({"naam": s['naam'], "gap_text": f"{gap:.1f} punten achterstand", "bullets": [f"Prijs: zak {drop_win:.1f}%-punt", f"Kwaliteit: {qual_hint}"]})

        overzicht_rows.append({"Scenario": s["naam"], "JDE (totaal)": round(jde_total, 1), "Concurrent (totaal)": round(comp_total, 1), "Status": status, "Max % duurder (gelijkspel)": max_over_pct_txt, "Kwaliteitsadvies (1 stap)": qual_hint})

    # Overzicht en downloads
    df_overzicht = pd.DataFrame(overzicht_rows).set_index("Scenario")
    st.subheader("Overzicht alle scenario's")
    st.dataframe(df_overzicht, use_container_width=True)
    st.subheader("📊 Samenvatting")
    st.write(f"- WIN: {wins}/{len(scenarios)}, DRAW: {draws}, LOSE: {losses}")
    st.write(f"- {price_easy} verlies-situaties: prijsactie voldoende")
    st.write(f"- {quality_easy} verlies-situaties: één kwaliteitsstap voldoende")

    csv = df_overzicht.to_csv(index=True)
    st.download_button("Download overzicht (CSV)", data=csv, file_name="winkans_overzicht.csv", mime="text/csv")

    summary_dict = {"headline": f"Wins:{wins} • Draws:{draws} • Losses:{losses} • Kwaliteit%:{kwaliteit_pct}% • Prijs%:{prijs_pct}%"}
    pdf_bytes = make_pdf(summary_dict, df_overzicht, scenario_advices)
    if pdf_bytes:
        st.download_button("📄 Download printbare adviespagina (PDF)", data=pdf_bytes, file_name="advies_winkans_bpkv.pdf", mime="application/pdf")
    else:
        st.info("PDF niet beschikbaar (reportlab ontbreekt).")

else:
    st.info("Klik op 'Bereken winkansen' om te starten.")

