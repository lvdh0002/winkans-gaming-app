import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Tender Analyse Tool", layout="wide")
st.title("🔍 Intuïtieve Tender Analyse Tool")

# --- Stap 1: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
# Prijs-Kwaliteit verhouding: gebruiker vult kwaliteit (%), prijs = 100 - kwaliteit
kwaliteit_pct = st.sidebar.number_input(
    "Kwaliteit (%) (vul één in)", min_value=0, max_value=100, value=60, step=1,
    help="Vul kwaliteit in; prijs wordt automatisch 100 - kwaliteit"
)
prijs_pct = 100 - kwaliteit_pct
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_pct}%\n- **Prijs:** {prijs_pct}%")

# Puntenschaal selectie
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
scale_label = st.sidebar.selectbox("Kies een schaal", options=list(scales.keys()))
if scale_label == "Custom...":
    custom_values = st.sidebar.text_input(
        "Voer eigen schaalwaarden in, gescheiden door komma's",
        value="0,25,50,75,100",
        help="Bij afwijkende beoordelingsschaal"
    )
    try:
        scale_values = [float(x.strip()) for x in custom_values.split(',')]
    except:
        st.sidebar.error("Ongeldige invoer. Gebruik komma's om getallen te scheiden.")
        scale_values = [0, 25, 50, 75, 100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

# --- Stap 2: Gunningscriteria ---
st.sidebar.header("Stap 2: Gunningscriteria")
# Aantal kwaliteitscriteria\ nnum_criteria = st.sidebar.selectbox(
  "Aantal kwaliteitscriteria (1-10)", list(range(1, 11)), index=3
)
criteria = [f"C{i+1}" for i in range(num_criteria)]

# Gewichten per subcriterium en automatische vertaling naar max punten
st.sidebar.subheader("Gewichten & Max punten per criterium")
kwaliteit_max_totaal = kwaliteit_pct * 10
weging_pct = {}
max_points_criteria = {}
for c in criteria:
    w = st.sidebar.number_input(
        f"Weging {c} (%)", min_value=0, max_value=100,
        value=int(100/num_criteria), key=f"w_{c}"
    )
    default_pts = int((w/100) * kwaliteit_max_totaal)
    mp = st.sidebar.number_input(
        f"Max punten {c}", min_value=1, value=default_pts, key=f"mp_{c}"
    )
    weging_pct[c] = w
    max_points_criteria[c] = mp

# Prijs: max punten automatisch op basis van prijs_pct*10, kan aanpassen
st.sidebar.markdown("---")
prijs_max_default = int(prijs_pct * 10)
max_price_points = st.sidebar.number_input(
    "Max punten Prijs", min_value=1, value=prijs_max_default, key="max_price"
)

# --- Stap 3: Verwachte scores Eigen partij ---
st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
# Kwaliteitsscores
st.sidebar.subheader("Kwaliteitsscores")
verwachte_scores_eigen = {}
for c in criteria:
    s = st.sidebar.selectbox(
        f"Score {c}", options=[str(x) for x in scale_values], key=f"score_eigen_{c}"
    )
    verwachte_scores_eigen[c] = float(s)

# Prijsscore op basis van % duurder dan goedkoopste
st.sidebar.subheader("Prijspositie")
margin_pct = st.sidebar.number_input(
    "% duurder dan goedkoopste", min_value=0.0, max_value=100.0, value=10.0, step=0.1
)
eigen_prijs_points = max_price_points * max(0, 1 - margin_pct/100)
st.sidebar.markdown(f"**Eigen Prijsscore:** {eigen_prijs_points:.1f} punten")

# --- Scenario invoer concurrenten ---
st.header("📥 Concurrentsituaties (max 15)")
num_scen = st.number_input(
    "Aantal situaties", min_value=1, max_value=15, value=3, step=1
)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input(
            "Naam concurrent", value=f"Concurrent {i+1}", key=f"naam{i}"
        )
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = 0.0
        if not is_cheapest:
            pct = st.number_input(
                "% duurder dan goedkoopste", min_value=0.0, max_value=100.0,
                value=margin_pct, key=f"pct{i}"
            )
        prijs_pts = max_price_points * (1 if is_cheapest else max(0, 1 - pct/100))
        kval_scores = {}
        for c in criteria:
            sc = st.selectbox(
                f"Score {c}", options=[str(x) for x in scale_values], key=f"score_{i}_{c}"
            )
            kval_scores[c] = float(sc)
        scenarios.append({"naam": naam, "prijs_pts": prijs_pts, "kval_scores": kval_scores})

# --- Analyse & Resultaten ---
st.header("📈 Resultaten")
if st.button("Bereken winkansen"):
    def score_to_points(score, max_pts):
        if max_scale > 10:
            return (score/100) * max_pts
        return (score/max_scale) * max_pts

    eigen_kval_pts = sum(
        score_to_points(verwachte_scores_eigen[c], max_points_criteria[c])
        for c in criteria
    )
    eigen_totaal = eigen_kval_pts + eigen_prijs_points

    results = []
    for s in scenarios:
        kval_p = sum(
            score_to_points(s['kval_scores'][c], max_points_criteria[c])
            for c in criteria
        )
        totaal = kval_p + s['prijs_pts']
        results.append({
            'Naam': s['naam'],
            'Kwaliteit': round(kval_p, 2),
            'Prijs': round(s['prijs_pts'], 2),
            'Totaal': round(totaal, 2)
        })

    df = pd.DataFrame(results).sort_values('Totaal', ascending=False)
    df.index = range(1, len(df) + 1)

    st.subheader("Overzicht scores")
    st.dataframe(df, use_container_width=True)

    st.subheader("Winkansen")
    for _, r in df.iterrows():
        if eigen_totaal > r['Totaal']:
            st.write(f"- {r['Naam']}: WINNEN ({eigen_totaal:.2f} > {r['Totaal']:.2f})")
        else:
            miss = r['Totaal'] - eigen_kval_pts
            perc = (miss / max_price_points) * 100
            st.write(
                f"- {r['Naam']}: VERLIEZEN, je mist {miss:.2f} prijspt "
                f"(±{perc:.1f}% van max)"
            )

    st.subheader("Benodigde prijspunten per situatie")
    for _, r in df.iterrows():
        need = r['Totaal'] - eigen_kval_pts
        if need < 0:
            need = 0
        perc = (need / max_price_points) * 100
        st.write(
            f"- {r['Naam']}: min {need:.2f} pt (±{perc:.1f}% van max)"
        )

    st.subheader("Eigen scores")
    st.write(f"- Kwaliteit: {eigen_kval_pts:.2f}")
    st.write(f"- Prijs: {eigen_prijs_points:.2f}")
    st.write(f"- Totaal: {eigen_totaal:.2f}")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")



