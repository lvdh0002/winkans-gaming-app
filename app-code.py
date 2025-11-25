import io
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.metric("Jouw totaalscore", f"{jde_total:.1f}")

def score_to_points(s, maxp, max_scale):
    # Altijd normaliseren op hoogste waarde van de gekozen schaal
    return (float(s) / float(max_scale)) * float(maxp)

def compute_price_route_for_draw(comp_total, your_quality_pts, max_price_points, current_margin_pct):
    """
    Geeft (margin_required_pct, drop_pct) voor gelijkspel.
    Als margin_required_pct < 0 => zelfs goedkoopste is niet genoeg (prijsroute faalt).
    """
    required_price_points = comp_total - your_quality_pts
    if required_price_points <= 0:
        # Je kwaliteit is al hoger dan comp_total; je kunt zelfs je prijs verhogen en nog gelijkspelen.
        margin_required_pct = 100.0  # feitelijk: alle marges toegestaan, cap op 100
    else:
        margin_required_pct = 100.0 * (1.0 - required_price_points / max_price_points)
    margin_required_pct = float(np.clip(margin_required_pct, 0.0, 100.0))
    drop_pct = current_margin_pct - margin_required_pct
    return margin_required_pct, drop_pct

def compute_price_route_for_win(comp_total, your_quality_pts, max_price_points, current_margin_pct):
    """
    Zelfde als draw, maar +0.01 marge voor 'win'.
    """
    required_price_points = (comp_total + 0.01) - your_quality_pts
    if required_price_points <= 0:
        margin_required_pct = 100.0
    else:
        margin_required_pct = 100.0 * (1.0 - required_price_points / max_price_points)
    margin_required_pct = float(np.clip(margin_required_pct, 0.0, 100.0))
    drop_pct = current_margin_pct - margin_required_pct
    return margin_required_pct, drop_pct

def best_one_step_quality_gain(criteria, scale_values, current_scores_dict, max_points_criteria, max_scale):
    """
    Vind de 'beste' (max puntenwinst) 1-stap kwaliteitsverbetering.
    Return: (criterium, current, next, gain) of None
    """
    best = None
    for c in criteria:
        cur = float(current_scores_dict[c])
        higher_steps = [x for x in scale_values if float(x) > cur]
        for nxt in higher_steps:
            gain = score_to_points(nxt, max_points_criteria[c], max_scale) - score_to_points(cur, max_points_criteria[c], max_scale)
            if best is None or gain > best[3]:
                best = (c, cur, float(nxt), float(gain))
    return best

def scenario_scorecard_figure(title, your_quality_pts, your_price_pts, comp_quality_pts, comp_price_pts):
    """
    Matplotlib stacked bars voor JOU vs CONCURRENT
    """
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    names = ["Jij", "Concurrent"]
    quality = [your_quality_pts, comp_quality_pts]
    price = [your_price_pts, comp_price_pts]
    ax.bar(names, quality, label="Kwaliteit", color="#4CAF50")
    ax.bar(names, price, bottom=quality, label="Prijs", color="#2196F3")
    ax.set_title(title)
    ax.set_ylabel("Punten")
    ax.legend(loc="upper right")
    ax.set_ylim(0, max(your_quality_pts + your_price_pts, comp_quality_pts + comp_price_pts) * 1.15)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return fig

def make_pdf(summary_dict, df_overzicht, scenario_details):
    """
    Bouw een printbare PDF-adviespagina (A4) met:
    - Kop & samenvatting (wins/draws/losses)
    - Tabel met kerninfo per scenario
    - Actie-adviezen per verlies-scenario
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    flow = []

    # Titel
    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)", styles["Title"]))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(summary_dict["headline"], styles["Normal"]))
    flow.append(Spacer(1, 12))

    # Overzichtstabel
    table_data = [["Scenario", "Status", "Jouw punten", "Concurrent", "Max % duurder (gelijkspel)", "Kwaliteitsadvies (1 stap)"]]
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
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 16))

    # Verlies-situaties adviezen
    if scenario_details:
        flow.append(Paragraph("Concrete acties bij verlies-situaties", styles["Heading2"]))
        flow.append(Spacer(1, 8))
        for d in scenario_details:
            flow.append(Paragraph(f"<b>{d['naam']}</b> — achterstand: {d['gap_text']}", styles["Heading3"]))
            for p in d["bullets"]:
                flow.append(Paragraph(f"• {p}", styles["Normal"]))
            flow.append(Spacer(1, 8))

    doc.build(flow)
    buf.seek(0)
    return buf.getvalue()

# --- Analyse & Resultaten (leek-proof, met acties, scorekaart & PDF) ---
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # 1) Jouw punten
    jde_quality_pts = sum(
        score_to_points(verwachte_scores_eigen[c], max_points_criteria[c], max_scale)
        for c in criteria
    )
    jde_price_pts = eigen_prijs_points
    jde_total = jde_quality_pts + jde_price_pts

    overzicht_rows = []
    scenario_advices = []
    wins = draws = losses = 0
    price_easy = 0
    quality_easy = 0

    st.subheader("Samenvatting per situatie (mensentaal)")
    for s in scenarios:
        comp_quality_pts = sum(
            score_to_points(s['kval_scores'][c], max_points_criteria[c], max_scale)
            for c in criteria
        )
        comp_price_pts = s['prijs_pts']
        comp_total = comp_quality_pts + comp_price_pts

        # Status
        if jde_total > comp_total:
            status, icon = "WIN", "✅"
            wins += 1
        elif jde_total < comp_total:
            status, icon = "LOSE", "❌"
            losses += 1
        else:
            status, icon = "DRAW", "⚠️"
            draws += 1

        # Kaartkop
        st.markdown(f"### {icon} {s['naam']} — {status}")
        st.write(f"**Jouw totaalscore:** {jde_total:.1f}  |  **Concurrent:** {comp_total:.1f}")

        # Scorekaart knop
        with st.expander("Toon visuele scorekaart"):
            fig = scenario_scorecard_figure(
                s['naam'],
                jde_quality_pts, jde_price_pts,
                comp_quality_pts, comp_price_pts
            )
            st.pyplot(fig, clear_figure=True)

        qual_hint = ""
        max_over_pct_txt = ""

        if status == "WIN":
            st.success("Je wint. Je huidige combinatie van kwaliteit en prijs is voldoende. Blijf dit niveau vasthouden.")
        elif status == "DRAW":
            st.info("Het is gelijkspel. Een kleine kwaliteitsstap of een bescheiden prijsdaling kan de doorslag geven.")
        else:
            # LOSE — routes naar winst
            gap = comp_total - jde_total
            gap_text = f"{gap:.1f} punten achterstand"

            # Prijs-route (gelijkspel & winst)
            margin_req_draw, drop_draw = compute_price_route_for_draw(comp_total, jde_quality_pts, max_price_points, margin_pct)
            margin_req_win, drop_win = compute_price_route_for_win(comp_total, jde_quality_pts, max_price_points, margin_pct)

            price_msgs = []
            if margin_req_draw == 0.0 and drop_draw > margin_pct:
                # betekent: zelfs 0% marge (goedkoopste) is niet genoeg -> prijsroute faalt
                price_msgs.append("**Prijs-route (alleen):** zelfs als je de goedkoopste bent, is gelijkspel niet haalbaar. Kijk naar kwaliteit.")
            else:
                if drop_draw > 0:
                    st.warning(
                        f"**Prijs-route (gelijkspel):** verlaag je prijs met **{drop_draw:.1f} %-punt** "
                        f"(van {margin_pct:.1f}% naar {margin_req_draw:.1f}%)."
                    )
                    price_easy += 1
                    max_over_pct_txt = f"{margin_req_draw:.1f}%"
                else:
                    st.info("**Prijs-route (gelijkspel):** je mag zelfs iets duurder zijn en nog gelijkspelen.")

                if drop_win > 0:
                    st.warning(
                        f"**Prijs-route (winst):** verlaag je prijs met **{drop_win:.1f} %-punt** "
                        f"(van {margin_pct:.1f}% naar {margin_req_win:.1f}%)."
                    )
                else:
                    st.info("**Prijs-route (winst):** je kunt al winnen zonder extra prijsdaling als je kwaliteit licht verbetert.")

            # Kwaliteit-route (één stap)
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
                quality_easy += 1
            else:
                # Combi-route: kies beste 1-stap kwaliteit en herbereken benodigde prijsdaling
                best_step = best_one_step_quality_gain(criteria, scale_values, verwachte_scores_eigen, max_points_criteria, max_scale)
                if best_step:
                    c, cur, nxt, gain = best_step
                    new_quality_pts = jde_quality_pts + gain
                    margin_req_win_combo, drop_win_combo = compute_price_route_for_win(comp_total, new_quality_pts, max_price_points, margin_pct)
                    st.info(
                        f"**Combi-route:** verhoog **{c}** van **{cur}** naar **{nxt}** (+{gain:.1f} ptn) "
                        f"én verlaag prijs met **{drop_win_combo:.1f} %-punt** "
                        f"(naar {margin_req_win_combo:.1f}%) om te winnen."
                    )
                    qual_hint = f"{c}: {cur}→{nxt}"
                    max_over_pct_txt = f"{margin_req_win_combo:.1f}%"
                else:
                    st.info("**Kwaliteit-route:** geen zinvolle één-stap verbetering mogelijk. Overweeg meerdere criteria of grotere prijsdaling.")

            scenario_advices.append({
                "naam": s['naam'],
                "gap_text": gap_text,
                "bullets": [
                    *(price_msgs),
                    *( [f"Kwaliteit: verhoog {qual_hint}"] if qual_hint else [] ),
                    *( [f"Max marge voor gelijkspel: {max_over_pct_txt}"] if max_over_pct_txt else [] ),
                ]
            })

        overzicht_rows.append({
            "Scenario": s["naam"],
            "JDE (totaal)": round(jde_total, 1),
            "Concurrent (totaal)": round(comp_total, 1),
            "Status": status,
            "Max % duurder (gelijkspel)": max_over_pct_txt,
            "Kwaliteitsadvies (1 stap)": qual_hint,
        })

    df_overzicht = pd.DataFrame(overzicht_rows).set_index("Scenario")

    # Overzichtstabel
    st.subheader("Overzicht alle scenario's")
    st.dataframe(df_overzicht, use_container_width=True)

    # Mensentaal samenvatting
    total = len(scenarios)
    st.subheader("📊 Samenvatting in mensentaal")
    st.write(f"- Je wint in **{wins} van {total}** situaties, gelijkspel in **{draws}**, verlies in **{losses}**.")
    st.write(f"- In **{price_easy}** verlies-situaties is een **puur prijs**-aanpassing (concreet %-punt verlagen) voldoende voor gelijkspel/winst.")
    st.write(f"- In **{quality_easy}** verlies-situaties is **één kwaliteitsstap** op de schaal voldoende om te winnen.")

    # Download CSV
    csv = df_overzicht.to_csv(index=True)
    st.download_button("Download overzicht (CSV)", data=csv, file_name="winkans_overzicht.csv", mime="text/csv")

    # PDF adviespagina
    summary_dict = {
        "headline": f"Wins: {wins}  •  Draws: {draws}  •  Losses: {losses}  •  Kwaliteit%: {kwaliteit_pct}%  •  Prijs%: {prijs_pct}%"
    }
    pdf_bytes = make_pdf(summary_dict, df_overzicht, scenario_advices)
    st.download_button("📄 Download printbare adviespagina (PDF)", data=pdf_bytes, file_name="advies_winkans_bpkv.pdf", mime="application/pdf")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
