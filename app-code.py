import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
st.title("Tool om winkansen te berekenen o.b.v. de BPKV-methode (Beste Prijs Kwaliteit Verhouding)")

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
st.header("Resultaten")
if st.button("Bereken winkansen"):
    # Functie om schaalscore naar punten te converteren
    def score_to_points(s, maxp):
        return (s/100)*maxp if max_scale>10 else (s/max_scale)*maxp

    # Bereken JDE's punten
    jde_quality_pts = sum(
        score_to_points(verwachte_scores_eigen[c], max_points_criteria[c])
        for c in criteria
    )
    jde_price_pts = eigen_prijs_points
    jde_total = jde_quality_pts + jde_price_pts

    # Vergelijk JDE met elke concurrent
    vergelijking = []
    for s in scenarios:
        comp_quality_pts = sum(
            score_to_points(s['kval_scores'][c], max_points_criteria[c])
            for c in criteria
        )
        comp_price_pts = s['prijs_pts']
        comp_total = comp_quality_pts + comp_price_pts
        # Bepaal status
        if jde_total > comp_total:
            status = 'WIN'
        elif jde_total < comp_total:
            status = 'LOSE'
        else:
            status = 'DRAW'
        vergelijking.append({
            'Scenario': s['naam'],
            'JDE (K+P)': f"{round(jde_quality_pts,1)}+{round(jde_price_pts,1)}={round(jde_total,1)}",
            'Comp (K+P)': f"{round(comp_quality_pts,1)}+{round(comp_price_pts,1)}={round(comp_total,1)}",
            'Status': status
        })
    df_verg = pd.DataFrame(vergelijking).set_index('Scenario')
    st.subheader("Vergelijking JDE vs scenario")
    st.table(df_verg)

        # Prijsadvies om te winnen
    st.subheader("Prijsadvies om te winnen")
    prijs_advies = []
    for row in vergelijking:
        if row['Status'] == 'LOSE':
            comp_tot = float(row['Comp (K+P)'].split('=')[-1])
            need_pts = comp_tot - jde_quality_pts + 0.01
            # bereken maximale allowed overpricing
            max_over_pct = (1 - need_pts/max_price_points) * 100
            # huidige overpricing = margin_pct
            # bereken hoeveel procent zakken
            drop_pct = margin_pct - max_over_pct
            prijs_advies.append({
                'Scenario': row['Scenario'],
                'Max % duurder dan goedkoopste': f"{max_over_pct:.1f}%",
                'Moet zakken met (%)': f"{drop_pct:.1f}%"
            })
    if prijs_advies:
        df_adv_prijs = pd.DataFrame(prijs_advies).set_index('Scenario')
        st.table(df_adv_prijs)
    else:
        st.write("JDE wint qua prijs in alle scenario's.")

    # Kwaliteitsadvies om te winnen bij gelijkblijvende prijs
    st.subheader("Kwaliteitsadvies om te winnen bij gelijkblijvende prijs")
("JDE wint qua prijs in alle scenario's.")

    # Kwaliteitsadvies om te winnen
st.subheader("Kwaliteitsadvies om te winnen bij gelijkblijvende prijs")
kwal_advies = []
   for row in vergelijking:
       if row['Status'] == 'LOSE':
           comp_tot = float(row['Comp (K+P)'].split('=')[-1])
           gap = comp_tot - jde_total + 0.01
           for c in criteria:
               current = verwachte_scores_eigen[c]
               for nxt in scale_values:
                   if nxt > current:
                       gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(current, max_points_criteria[c])
                       if gain >= gap:
                           kwal_advies.append({
                               'Scenario': row['Scenario'],
                               'Criterium': c,
                               'Huidig→Nodig': f"{current}→{nxt}",
                               'Extra punten': round(gain,1)
                           })
                           break
    if kwal_advies:
        df_adv_kw = pd.DataFrame(kwal_advies).set_index('Scenario')
        st.table(df_adv_kw)
    else:
        st.write("Geen enkele kwaliteitsverhoging in één stap is voldoende om te winnen.")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")


