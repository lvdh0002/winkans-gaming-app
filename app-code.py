import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekenen Tool", layout="wide")
st.title("Winkensen berkenen op basis van BPKV-methode (Beste Prijs Kwaliteit Verhouding)")

# Helper to track last changed field
if 'last_changed' not in st.session_state:
    st.session_state.last_changed = 'quality'
def set_last(field):
    st.session_state.last_changed = field

# --- Stap 1: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
col1, col2 = st.sidebar.columns(2)
with col1:
    st.number_input(
        "Kwaliteit (%)", min_value=0, max_value=100,
        key='quality_input', value=60, step=1,
        help="Vul kwaliteit in; prijs wordt automatisch 100 - kwaliteit",
        on_change=set_last, args=('quality',)
    )
with col2:
    st.number_input(
        "Prijs (%)", min_value=0, max_value=100,
        key='price_input', value=40, step=1,
        help="Vul prijs in; kwaliteit wordt automatisch 100 - prijs",
        on_change=set_last, args=('price',)
    )
# Compute paired values
auto_quality = st.session_state.quality_input
kwaliteit_pct = auto_quality
prijs_pct = 100 - auto_quality
# Display
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
scale_label = st.sidebar.selectbox("Kies een schaal", options=list(scales.keys()))
if scale_label == "Custom...":
    custom_values = st.sidebar.text_input(
        "Voer eigen schaalwaarden in, gescheiden door komma's",
        value="0,25,50,75,100",
        help="Bij afwijkende beoordelingsschaal"
    )
    try:
        scale_values = [float(x.strip()) for x in custom_values.split(',')]
    except Exception:
        st.sidebar.error("Ongeldige invoer. Gebruik komma's om getallen te scheiden.")
        scale_values = [0, 25, 50, 75, 100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

# --- Stap 2: Gunningscriteria ---
st.sidebar.header("Stap 2: Gunningscriteria")
# Aantal kwaliteitscriteria (1-10)
num_criteria = st.sidebar.selectbox(
    "Aantal kwaliteitscriteria (1-10)", list(range(1, 11)), index=3
)
criteria = [f"C{i+1}" for i in range(num_criteria)]

# Gewichten & Max punten per criterium
st.sidebar.subheader("Gewichten & Max punten per criterium")
weging_pct = {}
max_points_criteria = {}

for c in criteria:
    # Weging in % (moet samen gelijk zijn aan kwaliteit_pct)
    w = st.sidebar.number_input(
        f"Weging {c} (%)", min_value=0, max_value=kwaliteit_pct,
        value=int(kwaliteit_pct/num_criteria), key=f"w_{c}"
    )
    weging_pct[c] = w
    # Max punten = w% * 10 (dus 25% → 250 punten)
    default_pts = w * 10
    mp = st.sidebar.number_input(
        f"Max punten {c}", min_value=1, value=default_pts, key=f"mp_{c}"
    )
    max_points_criteria[c] = mp

# Controle: subcriteria-gewichten moeten optellen tot kwaliteit_pct
total_sub = sum(weging_pct.values())
st.sidebar.markdown(f"**Totaal subcriteria gewicht:** {total_sub}%  (moet = {kwaliteit_pct}%)")
if total_sub != kwaliteit_pct:
    st.sidebar.error("Subcriteria-gewichten moeten optellen tot het gekozen kwaliteit-percentage.")

# Prijs onder criteria
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Prijs gewicht:** {prijs_pct}%  **Max punten Prijs:** {prijs_pct*10:.0f}")
max_price_points = st.sidebar.number_input(
    "Max punten Prijs", min_value=1, value=int(prijs_pct*10), key="max_price"
)

# --- Stap 3: Verwachte scores Eigen partij ---
st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
verwachte_scores_eigen = {}
for c in criteria:
    s = st.sidebar.selectbox(
        f"Score {c}", options=[str(x) for x in scale_values], key=f"score_eigen_{c}"
    )
    verwachte_scores_eigen[c] = float(s)
# Prijspositie
margin_pct = st.sidebar.number_input(
    "% duurder dan goedkoopste", min_value=0.0, max_value=100.0,
    value=10.0, step=0.1
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


