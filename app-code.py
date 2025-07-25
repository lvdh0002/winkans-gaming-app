import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Tender Analyse Tool", layout="wide")
st.title("🔍 Intuïtieve Tender Analyse Tool")

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
auto_quality = st.session_state.quality_input
kwaliteit_pct = auto_quality
prijs_pct = 100 - auto_quality
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_pct}%  \n- **Prijs:** {prijs_pct}%")

# --- Puntenschaal selectie ---
st.sidebar.subheader("Puntenschaal voor beoordeling")
scales = {...}  # keep existing scales dict
# (omitted for brevity; on code implement full dict as before)
# Assume scale_values and max_scale defined here

# --- Stap 2: Gunningscriteria ---
st.sidebar.header("Stap 2: Gunningscriteria")
# Aantal kwaliteitscriteria\ nnum_criteria = ...
# criteria list as before
# Gewichten & Max punten per criterium
kwaliteit_max_totaal = kwaliteit_pct * 10
weging_pct = {}
max_points_criteria = {}
for c in criteria:
    w = st.sidebar.number_input(f"Weging {c} (%)", 0, kwaliteit_pct,
                                int(kwaliteit_pct/num_criteria), key=f"w_{c}")
    weging_pct[c] = w
    default_pts = w * 10
    mp = st.sidebar.number_input(f"Max punten {c}", 1, default_pts,
                                  default_pts, key=f"mp_{c}")
    max_points_criteria[c] = mp
# validate sum
# Prijs max points as before

# --- Stap 3: Verwachte scores Eigen partij ---
# as before compute verwachte_scores_eigen and eigen_prijs_points

# --- Scenario invoer concurrenten ---
# as before build scenarios list

# --- Analyse & Resultaten ---
st.header("📈 Resultaten")
if st.button("Bereken winkansen"):
    def score_to_points(score, max_pts):
        return (score/100)*max_pts if max_scale > 10 else (score/max_scale)*max_pts

    # Eigen scores
    eigen_quality_points = sum(
        score_to_points(verwachte_scores_eigen[c], max_points_criteria[c])
        for c in criteria
    )
    eigen_total = eigen_quality_points + eigen_prijs_points

    # Bereken concurrent scores
    data = []
    for s in scenarios:
        kval = sum(
            score_to_points(s['kval_scores'][c], max_points_criteria[c])
            for c in criteria
        )
        total = kval + s['prijs_pts']
        status = 'WIN' if eigen_total > total else 'LOSE'
        gap = max(0, total - eigen_total)
        data.append({ 'Naam': s['naam'], 'Status': status, 'Gap prijspt': round(gap,2) })
    df_summary = pd.DataFrame(data)

    # Overzicht verborgen winst/verlies
    st.subheader("Winst/Verlies Overzicht")
    st.table(df_summary)

    # Detail per situatie
    st.subheader("Detail per situatie")
    for row in data:
        naam = row['Naam']
        status = row['Status']
        st.write(f"**{naam}**: {status}")
        if status == 'LOSE':
            need = row['Gap prijspt']
            pct_need = round((need/max_price_points)*100,1)
            st.write(f"- Je mist {need} prijspt ({pct_need}% van max). Pas je prijs aan om te winnen.")
        st.write("---")

    # Analyse verbetering kwaliteit
    st.subheader("Wat als je beter scoort op kwaliteit?")
    # huidig per-criterium punten
    curr_q = {c: score_to_points(verwachte_scores_eigen[c], max_points_criteria[c])
              for c in criteria}
    improvements = []
    for s in scenarios:
        kval = sum(
            score_to_points(s['kval_scores'][c], max_points_criteria[c])
            for c in criteria
        )
        total = kval + s['prijs_pts']
        if eigen_total <= total:
            for c in criteria:
                gain = max_points_criteria[c] - curr_q[c]
                new_total = eigen_total + gain
                can_win = new_total > total
                improvements.append({
                    'Situatie': s['naam'],
                    'Criterium': c,
                    'Extra Q-punten nodig': round(gain,2),
                    'Win na max Cx': 'Yes' if can_win else 'No'
                })
    if improvements:
        df_imp = pd.DataFrame(improvements)
        st.table(df_imp)
    else:
        st.write("Je wint in alle scenario's, geen verbetering nodig.")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")

