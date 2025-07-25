import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Tender Analyse Tool", layout="wide")
st.title("🔍 Intuïtieve Tender Analyse Tool")

# --- Stap 1: Prijs-Kwaliteit Verdeling ---
st.sidebar.header("Stap 1: Prijs vs Kwaliteit")
# Verdeling slider in procenten
pk_ratio = st.sidebar.slider(
    "Verhouding Kwaliteit vs Prijs (%)",
    min_value=0,
    max_value=100,
    value=60,
    help="Verdeel 100% tussen kwaliteit en prijs"
)
kwaliteit_weging_pct = pk_ratio
prijs_weging_pct = 100 - pk_ratio
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_weging_pct}%\n- **Prijs:** {prijs_weging_pct}%")

# --- Puntenschaal selectie ---
st.sidebar.subheader("Puntenschaal voor beoordeling")
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-2,5-5-7,5-10": [0,2.5,5,7.5,10],
    "% -20%-40%-60%-80%-100%": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "0-30-50-80-100": [0,30,50,80,100],
    "0-30-50-70": [0,30,50,70],
    "Custom...": None
}
scale_label = st.sidebar.selectbox("Kies een schaal", options=list(scales.keys()))
if scale_label == "Custom...":
    custom = st.sidebar.text_input("Voer eigen schaalwaarden in, gescheiden door komma's", "0,25,50,75,100")
    scale_values = [float(x.strip()) for x in custom.split(',')]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

# --- Maximale punten op prijs ---
st.sidebar.subheader("Maximale Punten Prijs")
max_price_points = st.sidebar.number_input(
    "Max punten voor prijs", min_value=1, max_value=500, value=40, step=1
)

# --- Stap 2: Gunningscriteria ---
st.sidebar.header("Stap 2: Gunningscriteria")
num_criteria = st.sidebar.selectbox(
    "Aantal criteria (1-10)", list(range(1,11)), index=3
)
# Dynamisch de criteria labels
criteria = [f"C{i+1}" for i in range(num_criteria)]
st.sidebar.subheader("Gewichten en verwachte scores")
weging = {}
verwachte = {}
for c in criteria:
    cols = st.sidebar.columns(2)
    w = cols[0].number_input(f"Weging {c} (%)", min_value=0, max_value=100, value=round(100/num_criteria), key=f"w_{c}")
    s = cols[1].selectbox(f"Score {c}", options=[str(x) for x in scale_values], key=f"s_{c}")
    weging[c] = w
    try:
        verwachte[c] = float(s)
    except:
        verwachte[c] = 0.0

# Controle totaal weging kwaliteit
total_w = sum(weging.values())
st.sidebar.markdown(f"**Totaal weging kwaliteit:** {total_w}% (moet 100%)")

# --- Stap 3: Eigen prijspositie ---
st.sidebar.header("Stap 3: Eigen prijspozitie")
margin_pct = st.sidebar.slider(
    "Hoeveel procent duurder dan goedkoopste? (0-100%)", 0, 100, 10, help="We gaan uit van duurder dan goedkoopste"
)
eigen_prijs_score = max_price_points * max(0, 1 - margin_pct/100)
st.sidebar.markdown(f"**Eigen prijsscore:** {eigen_prijs_score:.1f} punten")

# --- Concurrentsituaties ---
st.header("📥 Voer concurrentsituaties in (max 15)")
num_scen = st.number_input("Aantal situaties", min_value=1, max_value=15, value=3)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input("Naam concurrent", value=f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = 0.0
        if not is_cheapest:
            pct = st.number_input("% duurder dan goedkoopste", min_value=0.0, max_value=100.0, value=margin_pct, key=f"pct{i}")
        price_score = max_price_points * (1 if is_cheapest else max(0, 1 - pct/100))
        # kwaliteit per criterium
        kval = {}
        for c in criteria:
            sc = st.selectbox(f"Score {c}", options=[str(x) for x in scale_values], key=f"k_{i}_{c}")
            kval[c] = float(sc)
        scenarios.append({"naam": naam, "prijs_score": price_score, "kwaliteit_scores": kval})

# --- Analyse knoppen ---
if st.button("Bereken winkansen"):
    # Functie om score naar punten om te zetten
    def score_to_points(score, max_pts):
        if max_scale > 10:
            return (score/100) * max_pts
        return (score/max_scale) * max_pts

    # Eigen kwaliteit totaal
    eigen_kwal_pnt = sum(score_to_points(verwachte[c], max_price_points if False else st.sidebar.number_input) for c in criteria)  # placeholder
    # TODO: implement eigen_kwal berekening
    # Concurrent berekeningen
    results = []
    for s in scenarios:
        kval_p = sum(score_to_points(s['kwaliteit_scores'][c], max_price_points if False else st.sidebar.number_input) for c in criteria)  # placeholder
        totaal = (kval_p * (kwaliteit_weging_pct/100)) + (s['prijs_score'] * (prijs_weging_pct/100))
        results.append({'Naam': s['naam'], 'Totaal': round(totaal,2)})

    df = pd.DataFrame(results).sort_values('Totaal', ascending=False)
    st.write(df)
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")


