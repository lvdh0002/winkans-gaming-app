import streamlit as st
import pandas as pd
import numpy as np

# Basisinstellingen en paginaconfiguratie
st.set_page_config(page_title="Tenderanalyse Tool", layout="wide")
st.title("🔍 Tenderanalyse Tool")

st.markdown("""
Deze tool berekent de winkans op basis van zowel **kwaliteit** als **prijs (in punten)**.
- **Kwaliteit:** Stel het aantal kwaliteitscriteria in (2–5), geef per criterium een weging (in procenten) én het maximale te behalen puntenaantal in. Vervolgens kun je voor elke inschrijver (en voor jezelf) een score kiezen op basis van een beoordelingsschaal.
- **Prijs:** Stel in de zijbalk het maximale te behalen puntenaantal op prijs in (bijv. 40). In de scenario’s voer je direct een prijsscore in.
- **Eigen prijsscore:** Kies of je jouw eigen prijsscore automatisch wilt instellen:
    - **+10% duurder:** resulteert in _36_ punten op prijs bij maximaal _40_ punten
    - **+15% duurder:** resulteert in _34_ punten op prijs bij maximaal _40_ punten
    - **+20% duurder:** resulteert in _32_ punten op prijs bij maximaal _40_ punten
    - **+25% duurder:** resulteert in _30_ punten op prijs bij maximaal _40_ punten
  Of kies "Handmatig invullen" om zelf een waarde in te voeren.
  
De output geeft je:
- Een overzicht van je eigen scores.
- Een tabel met per scenario de totaalpunten van de concurrenten.
- Per scenario: of je zou winnen of verliezen, en hoeveel prijspunten je eventueel mist.
- Een overzicht van de benodigde prijsscores per scenario (in absolute punten en als percentage van de max).
""")

# --- Sidebar Instellingen ---
st.sidebar.header("🔧 Instellingen")

# Aantal kwaliteitscriteria (excl. prijs)
num_criteria = st.sidebar.selectbox("Aantal kwaliteitscriteria (excl. prijs)", options=[2, 3, 4, 5], index=3)
criteria_labels = [f"W{i+1}" for i in range(num_criteria)]

# Wegingen voor kwaliteit
st.sidebar.subheader("Wegingen kwaliteit")
wegingen_kwaliteit = {}
for label in criteria_labels:
    w = st.sidebar.number_input(f"Weging {label} (%)", min_value=0, max_value=100, value=20, step=1, key=f"weg_{label}")
    wegingen_kwaliteit[label] = w
# Hier definiëren we de totale weging voor kwaliteit
weging_kwaliteit = sum(wegingen_kwaliteit.values())

# Weging voor prijs (automatisch zo dat totaal 100 is)
weging_prijs = st.sidebar.number_input("Weging prijs (%)", min_value=0, max_value=100, 
                                         value=100 - weging_kwaliteit, step=1)

st.sidebar.markdown("-----")
# Maximale punten per kwaliteitscriterium (éénmalig instellen)
st.sidebar.subheader("Maximale punten per kwaliteitscriterium")
max_punten_criteria = {}
for label in criteria_labels:
    mp = st.sidebar.number_input(f"Max punten {label}", min_value=10, max_value=300, value=100, step=10, key=f"mp_{label}")
    max_punten_criteria[label] = mp

# Maximum te behalen punten op prijs (bijv. 40 punten)
max_punten_prijs = st.sidebar.number_input("Max punten op prijs", min_value=10, max_value=500, value=40, step=1)

st.sidebar.markdown("-----")
# Beoordelingsschaal voor kwaliteitscriteria (invoer als opties)
st.sidebar.subheader("Beoordelingsschaal kwaliteit")
schaal_input = st.sidebar.text_input("Voer scoreopties in, gescheiden door komma's", value="0,25,50,75,100")
schaal_options = [float(x.strip()) for x in schaal_input.split(",") if x.strip().replace('.', '', 1).isdigit()]
max_schaal = max(schaal_options) if schaal_options else 100
st.sidebar.markdown("**Opmerking:** Als de maximale waarde > 10 is, gaan we ervan uit dat je met percentages werkt.")

# --- Scenario invoer voor concurrenten ---
st.markdown("---")
st.subheader("📥 Scenario invoer: Concurrenten")

num_scenario = st.number_input("Aantal scenario’s (concurrenten)", min_value=1, max_value=10, value=3)

# Invoer van scenario's (voor elke concurrent)
scenario_list = []
for i in range(int(num_scenario)):
    with st.expander(f"Scenario {chr(65 + i)}"):
        naam = st.text_input(f"Naam van concurrent {chr(65 + i)}", value=f"Concurrent {chr(65 + i)}", key=f"naam_{i}")
        # Voer direct een prijsscore in (in punten, maximaal max_punten_prijs)
        prijs_score = st.number_input(f"Prijsscore (in punten) voor {naam} (max {int(max_punten_prijs)})", 
                                      min_value=0, max_value=int(max_punten_prijs), value=int(max_punten_prijs), step=1, key=f"prijs_{i}")
        # Invoer kwaliteitsscores per criterium
        kwaliteit_scores = []
        for j in range(num_criteria):
            score_str = st.selectbox(f"Score {criteria_labels[j]} voor {naam}", options=[str(x) for x in schaal_options], key=f"score_{i}_{j}")
            try:
                score_val = float(score_str)
            except:
                score_val = 0.0
            kwaliteit_scores.append(score_val)
        scenario_list.append({"Naam": naam, "PrijsScore": prijs_score, "Kwaliteit": kwaliteit_scores})

# --- Eigen inschatting ---
st.markdown("---")
st.subheader("🤔 Eigen inschatting")

keuze_prijs = st.radio("Kies hoe je jouw eigen prijsscore wilt instellen:", 
                        options=["+10%", "+15%", "+20%", "+25%", "Handmatig invullen"], index=0)
if not keuze_prijs.startswith("+"):
    eigen_prijsscore = st.number_input("Eigen prijsscore (in punten)", min_value=0, max_value=int(max_punten_prijs), 
                                       value=int(max_punten_prijs), step=1, key="eigen_prijs")
else:
    # Gebruik vaste correcties: +10% = max - 4, +15% = max - 6, +20% = max - 8, +25% = max - 10
    aftrek_dict = {"+10%": 4, "+15%": 6, "+20%": 8, "+25%": 10}
    aftrek = aftrek_dict.get(keuze_prijs, 0)
    eigen_prijsscore = int(max_punten_prijs) - aftrek
st.write(f"**Jouw eigen prijsscore:** {eigen_prijsscore} punten (max = {int(max_punten_prijs)})")

# Invoer eigen kwaliteitsscores
st.markdown("**Vul je eigen kwaliteitsscores in:**")
eigen_scores = []
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
    # Functie: converteer een kwalitatieve score naar punten op basis van max per criterium.
    def calc_kwaliteitscore(score, max_punten):
        # Indien score in percentages (max_schaal > 10): (score/100)*max_punten, anders: (score/max_schaal)*max_punten.
        if max_schaal > 10:
            return (score / 100) * max_punten
        else:
            return (score / max_schaal) * max_punten

    # Bereken scores voor de concurrenten
    concurrenten_result = []
    for s in scenario_list:
        naam = s["Naam"]
        kwaliteit_total = 0
        for j, score in enumerate(s["Kwaliteit"]):
            mp = max_punten_criteria[criteria_labels[j]]
            kwaliteit_total += calc_kwaliteitscore(score, mp)
        prijsscore = s["PrijsScore"]
        totaal_score = (kwaliteit_total * (weging_kwaliteit / 100)) + (prijsscore * (weging_prijs / 100))
        concurrenten_result.append({"Naam": naam, "Prijsscore": prijsscore, "Kwaliteit": round(kwaliteit_total, 2), 
                                     "Totaal": round(totaal_score, 2)})
    
    # Bereken eigen kwaliteitsscore
    eigen_kwaliteit = 0
    for j, score in enumerate(eigen_scores):
        mp = max_punten_criteria[criteria_labels[j]]
        eigen_kwaliteit += calc_kwaliteitscore(score, mp)
    eigen_totaal = (eigen_kwaliteit * (weging_kwaliteit / 100)) + (eigen_prijsscore * (weging_prijs / 100))
    
    # Maak overzichtstabel van scenario's
    df_results = pd.DataFrame(concurrenten_result)
    df_results.sort_values(by="Totaal", ascending=False, inplace=True)
    df_results.reset_index(drop=True, inplace=True)
    df_results.index += 1
    
    st.markdown("### Overzicht scenario’s en winkansen")
    st.write("Hieronder zie je de totale scores van de concurrenten. Vergelijk jouw totaal met die van de concurrenten:")
    st.dataframe(df_results[["Naam", "Prijsscore", "Kwaliteit", "Totaal"]], use_container_width=True)
    
    # Winkansen per scenario: bepalen of jouw totaal hoger is, zo niet, hoeveel extra prijspunten je nodig hebt.
    st.markdown("#### Winkansen per scenario")
    winkans_lijst = []
    for r in concurrenten_result:
        if eigen_totaal > r["Totaal"]:
            winkans_lijst.append(f"{r['Naam']}: WINNEN (jouw totaal {eigen_totaal:.2f} > {r['Totaal']:.2f})")
        else:
            extra_prijs = r["Totaal"] - (eigen_kwaliteit * (weging_kwaliteit / 100))
            if extra_prijs < 0:
                extra_prijs = 0
            perc_extra = (extra_prijs / max_punten_prijs) * 100
            winkans_lijst.append(f"{r['Naam']}: VERLIEZEN; je mist {extra_prijs:.2f} prijspunten (±{perc_extra:.1f}% van max).")
    for w in winkans_lijst:
        st.write("- " + w)
    
    # Overzicht benodigde prijsscores per scenario
    st.markdown("### Overzicht benodigde prijsscores per scenario")
    prijsscore_overzicht = []
    for r in concurrenten_result:
        benodigd = r["Totaal"] - (eigen_kwaliteit * (weging_kwaliteit / 100))
        if benodigd < 0:
            benodigd = 0
        perc_verschil = (benodigd / max_punten_prijs) * 100
        prijsscore_overzicht.append(f"{r['Naam']}: Minimaal {benodigd:.2f} punten op prijs (±{perc_verschil:.1f}% van max).")
    for p in prijsscore_overzicht:
        st.write("- " + p)
    
    # Overzicht eigen scores
    st.markdown("### Jouw eigen ingevulde scores")
    st.write(f"**Eigen prijsscore:** {eigen_prijsscore} punten")
    st.write(f"**Eigen kwaliteitsscore:** {eigen_kwaliteit:.2f} punten")
    st.write(f"**Totaal:** {eigen_totaal:.2f} punten")
    
    st.markdown("---")
    st.caption("Tip: Maak een screenshot of exporteer de pagina als PDF voor archivering.")
    
else:
    st.info("Klik op 'Analyseer' om de resultaten te berekenen.")

