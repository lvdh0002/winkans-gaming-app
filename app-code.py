import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Tenderanalyse Tool", layout="wide")
st.title("🔍 Tenderanalyse Tool")

st.markdown("""
Deze tool berekent jouw tenderpuntenscore op basis van zowel kwaliteit als prijs (in punten).  
- **Kwaliteit:** Stel het aantal kwaliteitscriteria in (2–5) en geef per criterium de weging en jouw of de concurrent's score op basis van een beoordelingsschaal (bijv. 0,25,50,75,100 of 0,20,40,60,80,100 of 2,4,6,8,10).  
- **Prijs:** Stel de maximale te behalen punten op prijs in (bijv. 40). In de scenario’s voer je direct een prijsscore in (maximaal dit maximum).  
- **Eigen prijsscore:** Kies of je jouw prijsscore automatisch wilt instellen op +10%, +15%, +20% of +25% duurder dan de laagste (die dan respectievelijk max-4, max-6, max-8 of max-10 punten oplevert) of dat je een handmatige score wilt invullen.  
- De output geeft een overzicht van jouw eigen ingevulde scores, een scenario-overzicht met winkansen, en per scenario de benodigde prijsscore zodat je zou winnen.
""")

# --- Sidebar instellen ---
st.sidebar.header("🔧 Instellingen")

# Aantal kwaliteitscriteria kiezen
num_criteria = st.sidebar.selectbox("Aantal kwaliteitscriteria (excl. prijs)", options=[2, 3, 4, 5], index=3)
criteria_labels = [f"W{i+1}" for i in range(num_criteria)]

# Wegingen instellen
st.sidebar.subheader("Wegingen")
wegingen_kwaliteit = {}
total_quality_weight = 0
for label in criteria_labels:
    w = st.sidebar.number_input(f"Weging {label} (%)", min_value=0, max_value=100, value=20, step=1, key=f"weg_{label}")
    wegingen_kwaliteit[label] = w
    total_quality_weight += w

weging_prijs = st.sidebar.number_input("Weging prijs (%)", min_value=0, max_value=100, 
                                         value=100 - total_quality_weight, step=1)

# Maximum te behalen punten op prijs
max_punten_prijs = st.sidebar.number_input("Max punten op prijs", min_value=10, max_value=500, value=40, step=1)

# Beoordelingsschaal kwaliteitscriteria (handmatige invoer)
st.sidebar.subheader("Beoordelingsschaal kwaliteit")
schaal_input = st.sidebar.text_input("Voer scoreopties in, gescheiden door komma's", value="0,25,50,75,100")
schaal_options = [float(x.strip()) for x in schaal_input.split(",") if x.strip().replace('.', '', 1).isdigit()]
max_schaal = max(schaal_options) if schaal_options else 100

st.sidebar.markdown("**Opmerking:** Als de maximale waarde > 10 is, gaan we ervan uit dat je in percentages werkt.")

st.markdown("---")
st.subheader("📥 Scenario invoer: Concurrenten")
num_scenario = st.number_input("Aantal scenario’s (concurrenten)", min_value=1, max_value=10, value=3)

# Invoer concurrenten
scenario_list = []
for i in range(int(num_scenario)):
    with st.expander(f"Scenario {chr(65 + i)}"):
        naam = st.text_input(f"Naam concurrent {chr(65 + i)}", value=f"Concurrent {chr(65 + i)}", key=f"naam_{i}")
        # In dit geval voer je direct een puntenwaarde in voor de prijs (max max_punten_prijs)
        prijs_score = st.number_input(f"Prijsscore (punten) voor {naam} (max {max_punten_prijs})", 
                                      min_value=0.0, max_value=float(max_punten_prijs), value=float(max_punten_prijs), step=0.5, key=f"prijs_{i}")
        # Kwaliteitsscores per criterium
        kwaliteit_scores = []
        for j in range(num_criteria):
            score = st.selectbox(f"Score {criteria_labels[j]} voor {naam}", options=[str(x) for x in schaal_options], key=f"score_{i}_{j}")
            try:
                score_val = float(score)
            except:
                score_val = 0.0
            kwaliteit_scores.append(score_val)
        scenario_list.append({"Naam": naam, "PrijsScore": prijs_score, "Kwaliteit": kwaliteit_scores})

st.markdown("---")
st.subheader("🤔 Eigen inschatting")
# Eigen prijsscore: kies of deze wordt ingesteld via een percentage of handmatig
keuze_prijs = st.radio("Kies hoe je jouw prijsscore wil instellen:", 
                        options=["+10%", "+15%", "+20%", "+25%", "Handmatig invullen"])
laagste_prijsscore = min([s["PrijsScore"] for s in scenario_list]) if scenario_list else max_punten_prijs

if not keuze_prijs.startswith("+"):
    eigen_prijsscore = st.number_input("Eigen prijsscore (in punten)", min_value=0.0, max_value=float(max_punten_prijs), 
                                       value=float(max_punten_prijs), step=0.5)
else:
    # Bij keuze +10% geeft dat bijvoorbeeld max - 4 punten, +15% = max - 6, +20% = max - 8, +25% = max - 10.
    perc_dict = {"+10%": 4, "+15%": 6, "+20%": 8, "+25%": 10}
    aftrek = perc_dict.get(keuze_prijs, 0)
    eigen_prijsscore = max_punten_prijs - aftrek
st.write(f"**Berekening:** Bij een maximum van {max_punten_prijs} punten, resulteert dit in een eigen prijsscore van {eigen_prijsscore} punten.")

# Eigen kwaliteitsscores
eigen_scores = []
st.markdown("**Vul je eigen kwaliteitsscores in:**")
for j in range(num_criteria):
    s = st.selectbox(f"Score {criteria_labels[j]} (eigen inschatting)", options=[str(x) for x in schaal_options], key=f"eigen_{j}")
    try:
        eigen_score_val = float(s)
    except:
        eigen_score_val = 0.0
    eigen_scores.append(eigen_score_val)

# --- Berekeningen ---
st.markdown("---")
st.subheader("📈 Resultaten")

if st.button("Analyseer"):
    # Functie: converteer kwaliteitsscore naar punten op basis van beoordelingsschaal
    def calc_kwaliteitscore(score, max_punten):
        # Indien schaal > 10, beschouwen we het als percentages, anders als punten.
        if max_schaal > 10:
            return (score / 100) * max_punten
        else:
            return (score / max_schaal) * max_punten

    # Bereken scores voor concurrenten
    concurrenten_result = []
    for s in scenario_list:
        naam = s["Naam"]
        kwaliteit_total = 0
        for j, score in enumerate(s["Kwaliteit"]):
            # Bereken per criterium de gewogen kwaliteitsscore
            kwaliteit_total += calc_kwaliteitscore(score, max_punten_per_criterium = st.sidebar.number_input(f"Max punten {criteria_labels[j]} (voor {naam})", 
                                                                                                              min_value=10, max_value=300, value=100, step=10, key=f"max_{naam}_{criteria_labels[j]}"))
        prijsscore = s["PrijsScore"]
        totaal_score = (kwaliteit_total * (weging_kwaliteit / 100)) + (prijsscore * (weging_prijs / 100))
        concurrenten_result.append({"Naam": naam, "Prijsscore": prijsscore, "Kwaliteit": round(kwaliteit_total, 2), 
                                    "Totaal": round(totaal_score, 2)})
    
    # Bereken eigen scores
    # Voor de eigen kwaliteitspunten kun je ook voor iedere criteria een max aantal punten (input) bepalen; hiervoor gebruiken we dezelfde methode
    eigen_kwaliteit = 0
    for j, score in enumerate(eigen_scores):
        eigen_kwaliteit += calc_kwaliteitscore(score, max_punten_per_criterium = st.sidebar.number_input(f"Max punten {criteria_labels[j]} (eigen)", 
                                                                                                             min_value=10, max_value=300, value=100, step=10, key=f"max_eigen_{criteria_labels[j]}"))
    eigen_totaal = (eigen_kwaliteit * (weging_kwaliteit / 100)) + (eigen_prijsscore * (weging_prijs / 100))
    
    # Maak DataFrame voor output
    df_results = pd.DataFrame(concurrenten_result)
    df_results.sort_values(by="Totaal", ascending=False, inplace=True)
    df_results.reset_index(drop=True, inplace=True)
    df_results.index += 1

    st.markdown("### Overzicht scenario’s en winkansen")
    st.write("Hieronder zie je per scenario de totale score van de concurrenten en jouw eigen score. \nKlik op ‘Analyseer’ om de berekening te laten uitvoeren.")
    st.dataframe(df_results[["Naam", "Prijsscore", "Kwaliteit", "Totaal"]], use_container_width=True)
    
    # Winkans vergelijken: Per scenario aangeven of jouw eigen score hoger is, en zo niet, hoeveel punten je tekortkomt.
    st.markdown("#### Winkansen per scenario")
    winkans_lijst = []
    for r in concurrenten_result:
        if eigen_totaal > r["Totaal"]:
            winkans_lijst.append(f"{r['Naam']}: Je wint deze scenario (jouw totaalscore {eigen_totaal:.2f} > {r['Totaal']:.2f}).")
        else:
            # Bereken de benodigde extra prijspunten (aangenomen dat kwaliteitsscore vast blijft)
            benodigde_prijs = r["Totaal"] - (eigen_kwaliteit * (weging_kwaliteit / 100))
            if benodigde_prijs < 0:
                benodigde_prijs = 0
            # Omrekenen naar percentage op basis van max_punten_prijs
            perc_diff = (benodigde_prijs / max_punten_prijs) * 100
            winkans_lijst.append(f"{r['Naam']}: Je verliest; je hebt minimaal een prijsscore van {benodigde_prijs:.2f} nodig (±{perc_diff:.1f}% van de max).")
    
    for s in winkans_lijst:
        st.write("- " + s)
    
    st.markdown("### Overzicht benodigde prijsscores per scenario")
    st.write("Voor elk scenario wordt berekend wat jouw benodigde prijsscore moet zijn om net te winnen, uitgedrukt in punten en als percentage van de maximale prijsscore.")
    prijsscore_overzicht = []
    for r in concurrenten_result:
        benodigde_prijs = r["Totaal"] - (eigen_kwaliteit * (weging_kwaliteit / 100))
        if benodigde_prijs < 0:
            benodigde_prijs = 0
        perc_diff = (benodigde_prijs / max_punten_prijs) * 100
        prijsscore_overzicht.append(f"{r['Naam']}: Je hebt minimaal {benodigde_prijs:.2f} punten nodig, oftewel ±{perc_diff:.1f}% van de max.")
    
    for s in prijsscore_overzicht:
        st.write("- " + s)
    
    st.markdown("### Jouw eigen ingevulde scores")
    st.write(f"**Eigen prijsscore:** {eigen_prijsscore} punten")
    st.write(f"**Eigen kwaliteitsscore:** {eigen_kwaliteit:.2f} punten")
    st.write(f"**Jouw totaal:** {eigen_totaal:.2f} punten")
    
    st.markdown("---")
    st.caption("Tip: maak een screenshot of exporteer de pagina als PDF voor archivering.")
    
else:
    st.info("Klik op 'Analyseer' om de resultaten te berekenen.")
