import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Tender Analyse Tool", layout="wide")
st.title("🔍 Intuïtieve Tender Analyse Tool")

# --- Stap 1: Beoordelingsmethodiek ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
col1, col2 = st.sidebar.columns(2)
with col1:
    kwaliteit_pct = st.number_input(
        "Kwaliteit (%)", min_value=0, max_value=100,
        value=60, step=1,
        help="Vul kwaliteit in; prijs wordt automatisch 100 - kwaliteit",
        key="quality_input"
    )
with col2:
    prijs_pct = st.number_input(
        "Prijs (%)", min_value=0, max_value=100,
        value=40, step=1,
        help="Vul prijs in; kwaliteit wordt automatisch 100 - prijs",
        key="price_input"
    )
# Synchroniseer
if st.session_state.quality_input + st.session_state.price_input != 100:
    # als kwaliteit net is aangepast
    if st.session_state.quality_input != kwaliteit_pct:
        prijs_pct = 100 - kwaliteit_pct
        st.session_state.price_input = prijs_pct
    else:
        kwaliteit_pct = 100 - prijs_pct
        st.session_state.quality_input = kwaliteit_pct
# Toon
st.sidebar.markdown(f"- **Kwaliteit:** {kwaliteit_pct}%  \n- **Prijs:** {prijs_pct}%")

# --- Puntenschaal selectie ---
st.sidebar.subheader("Puntenschaal voor beoordeling")
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-2,5-5-7,5-10": [0,2.5,5,7.5,10],
    "0%-20%-40%-60%-80%-100%": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "0-30-50-80-100": [0,30,50,80,100],
    "0-30-50-70": [0,30,50,70],
    "Custom...": None
}
scale_label = st.sidebar.selectbox("Kies een schaal", list(scales.keys()))
if scale_label == "Custom...":
    vals = st.sidebar.text_input("Eigen schaal (komma-gescheiden)", "0,25,50,75,100")
    try:
        scale_values = [float(x) for x in vals.split(",")]
    except:
        st.sidebar.error("Ongeldige schaal, gebruik getallen gescheiden door komma.")
        scale_values = [0,25,50,75,100]
else:
    scale_values = scales[scale_label]
max_scale = max(scale_values)

# --- Stap 2: Gunningscriteria ---
st.sidebar.header("Stap 2: Gunningscriteria")
num_criteria = st.sidebar.selectbox("Aantal kwaliteitscriteria (1-10)", list(range(1,11)), index=3)
criteria = [f"C{i+1}" for i in range(num_criteria)]

st.sidebar.subheader("Gewichten & Max punten per criterium")
weging_pct = {}
max_points_criteria = {}
for c in criteria:
    w = st.sidebar.number_input(f"Weging {c} (%)", min_value=0, max_value=kwaliteit_pct,
                                 value=int(kwaliteit_pct/num_criteria), key=f"w_{c}")
    weging_pct[c] = w
    default_pts = w * 10
    mp = st.sidebar.number_input(f"Max punten {c}", min_value=1, value=default_pts, key=f"mp_{c}")
    max_points_criteria[c] = mp
# controle
total_sub = sum(weging_pct.values())
st.sidebar.markdown(f"**Totaal KG-gewichten:** {total_sub}% (moet = {kwaliteit_pct}% )")
if total_sub != kwaliteit_pct:
    st.sidebar.error("Subcriteria-gewichten moeten optellen tot het kwaliteit-percentage.")

# prijs punten
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Prijs gewicht:** {prijs_pct}%  **Max prijspt:** {prijs_pct*10:.0f}")
max_price_points = st.sidebar.number_input("Max punten Prijs", min_value=1, value=int(prijs_pct*10), key="max_price")

# --- Stap 3: Verwachte scores Eigen partij ---
st.sidebar.header("Stap 3: Verwachte scores Eigen partij")
verwachte_scores_eigen = {}
for c in criteria:
    score = st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}")
    verwachte_scores_eigen[c] = float(score)
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste", 0.0,100.0,10.0,0.1)
eigen_prijs_points = max_price_points * (1 - margin_pct/100)
st.sidebar.markdown(f"**Eigen Prijsscore:** {eigen_prijs_points:.1f}")

# --- Scenario invoer concurrenten ---
st.header("📥 Concurrentsituaties (max 15)")
num_scen = st.number_input("Aantal situaties",1,15,3,1)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Is goedkoopste?", key=f"cheap{i}")
        pct = st.number_input("% duurder dan goedkoopste",0.0,100.0,margin_pct,0.1, key=f"pct{i}") if not is_cheapest else 0
        prijs_pts = max_price_points * (1 if is_cheapest else 1-pct/100)
        kval_scores = {c: float(st.selectbox(f"Score {c}",[str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam":naam,"prijs_pts":prijs_pts,"kval_scores":kval_scores})

# --- Analyse & Resultaten ---
st.header("📈 Resultaten")
if st.button("Bereken winkansen"):
    def score_to_points(s,maxp): return (s/100)*maxp if max_scale>10 else (s/max_scale)*maxp

    # eigen
    eigen_q_pts = sum(score_to_points(verwachte_scores_eigen[c],max_points_criteria[c]) for c in criteria)
    eigen_total = eigen_q_pts + eigen_prijs_points

    # samenvatting
    summary = []
    for s in scenarios:
        kval = sum(score_to_points(s['kval_scores'][c],max_points_criteria[c]) for c in criteria)
        tot = kval + s['prijs_pts']
        status = 'WIN' if eigen_total>tot else 'LOSE'
        gap = max(0, tot-eigen_total)
        summary.append({'Naam':s['naam'],'Status':status,'Gap prijspt':round(gap,2)})
    df_sum = pd.DataFrame(summary)
    st.subheader("Winst/Verlies Overzicht")
    st.table(df_sum)

    # detail
    st.subheader("Detail per situatie")
    for row in summary:
        st.markdown(f"**{row['Naam']}**: {row['Status']}")
        if row['Status']=='LOSE':
            need=row['Gap prijspt']; pct_need=round((need/max_price_points)*100,1)
            st.write(f"- Mist {need} prijspt (~{pct_need}% van max). Pas prijs aan.")
        st.write('---')

    # wat als kwaliteit beter?
    st.subheader("Wat als je beter scoort op kwaliteit?")
    curr_q = {c: score_to_points(verwachte_scores_eigen[c],max_points_criteria[c]) for c in criteria}
    improvements=[]
    for s in scenarios:
        kval=sum(score_to_points(s['kval_scores'][c],max_points_criteria[c]) for c in criteria)
        tot=kval+s['prijs_pts']
        if eigen_total<=tot:
            for c in criteria:
                gain=max_points_criteria[c]-curr_q[c]
                new_tot=eigen_total+gain
                improvements.append({'Situatie':s['naam'],'Criterium':c,'Extra Q-punten':round(gain,2),'Win na max Cx':'Yes' if new_tot>tot else 'No'})
    if improvements:
        st.table(pd.DataFrame(improvements))
    else:
        st.write("Je wint in alle scenario's.")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")

