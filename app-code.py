import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Tenderanalyse Tool", layout="wide")
st.title("🔍 Tenderanalyse Tool")

st.markdown("""
Deze tool laat je op basis van meerdere scenario’s berekenen:
- Jouw eigen ingevulde scores versus concurrenten.
- Overzicht per scenario met winkansen en de benodigde prijs: hoeveel duurder mag je maximaal zijn.
- Overzicht van de benodigde prijsscores en het procentuele verschil t.o.v. de maximale punten op prijs.
""")

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

weging_prijs = st.sidebar.number_input("Weging prijs (%)", min_value=0, max_value=100, value=100 - total_quality_weight, step=1)

# Beoordelingsschaal instellen (handmatige invoer, dus 5 of 6 opties)
st.sidebar.subheader("Beoordelingsschaal kwaliteit")
schaal_input = st.sidebar.text_input("Opties gescheiden door komma's (bv. 0,25,50,75,100)", value="0,25,50,75,100")
schaal_options = [float(x.strip()) for x in schaal_input.split(",") if x.strip().replace('.', '', 1).isdigit()]
max_schaal = max(schaal_options) if schaal_options else 100  # dit bepaalt of we in percentages werken (max > 10 meestal) of een puntenchaal

st.sidebar.markdown("**Opmerking:** Als de maximale waarde >10 is, gaan we ervan uit dat er met percentages wordt gewerkt.")


st.markdown("---")
st.subheader("📥 Scenario invoer: Concurrenten")

# Invoer aantal scenario's
num_scenarios = st.number_input("Aantal scenario's (concurrenten)", min_value=1, max_value=10, value=3)

# Lijst voor scenario invoer
scenario_list = []
for i in range(int(num_scenarios)):
    with st.expander(f"Scenario {chr(65 + i)}"):
        naam = st.text_input(f"Naam concurrent {chr(65 + i)}", value=f"Concurrent {chr(65 + i)}", key=f"naam_{i}")
        prijs = st.number_input(f"Inschrijvingsprijs (in euro's) voor {naam}", min_value=0.0, value=100000.0, step=1000.0, key=f"prijs_{i}")
        # Invoer kwaliteitsscores per criterium
        kwaliteit_scores = []
        for j in range(num_criteria):
            score = st.selectbox(f"Score {criteria_labels[j]} voor {naam}", options=[str(x) for x in schaal_options],
                                 key=f"score_{i}_{j}")
            # Converteer naar float
            try:
                score_val = float(score)
            except:
                score_val = 0.0
            kwaliteit_scores.append(score_val)
        scenario_list.append({"Naam": naam, "Prijs": prijs, "Kwaliteit": kwaliteit_scores})

st.markdown("---")
st.subheader("🤔 Eigen inschatting")

# Eigen prijsscore: keuze of door procentuele verhoging of handmatig
keuze_prijs = st.radio("Kies hoe je jouw eigen prijs wil bepalen:", 
                        options=["+10%", "+15%", "+20%", "+25%", "Handmatig invullen"])
laagste_prijs = min([s["Prijs"] for s in scenario_list]) if scenario_list else 0
if not keuze_prijs.startswith("+"):
    eigen_prijs = st.number_input("Eigen inschrijvingsprijs (in euro's)", min_value=0.0, value=110000.0, step=1000.0)
else:
    perc = int(keuze_prijs.replace("+", "").replace("%", ""))
    eigen_prijs = round(laagste_prijs * (1 + perc/100), 2)
st.write(f"**Berekening:** Met de laagste prijs van {laagste_prijs:.2f} resulteert dit in een eigen prijs van {eigen_prijs:.2f} euro.")

# Eigen kwaliteitsscores
eigen_scores = []
st.markdown("**Vul je eigen scores in:**")
for j in range(num_criteria):
    s = st.selectbox(f"Score {criteria_labels[j]} (eigen inschatting)", options=[str(x) for x in schaal_options], key=f"eigen_{j}")
    try:
        eigen_score_val = float(s)
    except:
        eigen_score_val = 0.0
    eigen_scores.append(eigen_score_val)


# ------------------------------------------
st.markdown("---")
st.subheader("📈 Resultaten")

if st.button("Analyseer"):
    # Berekening 'score' per criterium
    # We gaan ervan uit dat als max_schaal > 10, het percentages zijn, dus normale verhouding (score/100)*max punten,
    # Anders: (score / max_schaal)*max punten.
    def bereken_kwaliteitsscore(score, max_punten):
        if max_schaal > 10:
            return (score / 100) * max_punten
        else:
            return (score / max_schaal) * max_punten
    
    # Voor concurrenten
    resultaten = []
    for s in scenario_list:
        naam = s["Naam"]
        prijs = s["Prijs"]
        # Hier kan je per criterium de maximum punten per criterium instellen (invoer via zijbalk)
        kwaliteit_total = 0
        for j, score in enumerate(s["Kwaliteit"]):
            kwaliteit_total += bereken_kwaliteitsscore(score, max_punten_per_criterium[j])
        prijsscore = (laagste_prijs / prijs) * max_punten_prijs if prijs > 0 else 0
        totaal_score = (kwaliteit_total * (weging_kwaliteit/100)) + (prijsscore * (weging_prijs/100))
        resultaten.append({"Naam": naam, "Prijs": prijs, "Kwaliteit": round(kwaliteit_total,2), 
                           "Prijsscore": round(prijsscore,2), "Totaal": round(totaal_score,2)})
    
    # Eigen score
    eigen_kwaliteit = 0
    for j, score in enumerate(eigen_scores):
        eigen_kwaliteit += bereken_kwaliteitsscore(score, max_punten_per_criterium[j])
    eigen_prijsscore = (laagste_prijs / eigen_prijs) * max_punten_prijs if eigen_prijs > 0 else 0
    eigen_totaal = (eigen_kwaliteit * (weging_kwaliteit/100)) + (eigen_prijsscore * (weging_prijs/100))
    
    # Vergelijk en maak output tabellen
    df_results = pd.DataFrame(resultaten)
    df_results.sort_values(by="Totaal", ascending=False, inplace=True)
    df_results.reset_index(drop=True, inplace=True)
    df_results.index += 1

    st.markdown("### Overzicht scenario’s en winkansen")
    st.write("De volgende tabel toont per scenario de totale score van de concurrenten. Naast jouw eigen score (onderaan) wordt getoond in welke scenario’s je een reële winkans hebt:")
    # Bepaal scenario waar eigen totaal groter is dan de score van de concurrent, of binnen een marge zoals in jouw originele code.
    winkans_scenario = []
    for r in resultaten:
        # We hanteren de volgende logica: als de concurrent score hoger is dan jouw eigen score, win je niet; als lager, dan bepaal je welk prijspercentage nodig is
        if eigen_totaal > r["Totaal"]:
            winkans_scenario.append(f"{r['Naam']}: je wint, aangezien jouw score ({eigen_totaal:.2f}) hoger is dan {r['Totaal']:.2f}")
        else:
            # bereken verschil in score door om te rekenen naar prijspunt verschil; dit is een simplistische weergave\n
            winkans_scenario.append(f"{r['Naam']}: je verliest (concurrent heeft {r['Totaal']:.2f} vs. jouw {eigen_totaal:.2f})")
    
    for s in winkans_scenario:
        st.write("- " + s)
    
    st.markdown("### Overzicht benodigde prijsscores")
    st.write("Voor elk scenario berekenen we de benodigde prijsscore zodat je net zou winnen, en reken we om hoeveel procent duurder je maximaal mag zijn (aangenomen dat de maximale score op prijs gelijk is aan de in de instellingen ingevoerde waarde).")
    prijsscore_overzicht = []
    for r in resultaten:
        # Bereken de benodigde prijsscore: het verschil tussen de concurrent en jouw kwaliteit is het duimpunt voor prijscompensatie.
        # In de originele code werd dit als volgt berekend: (concurrent score - kwaliteit van eigen) / prijsweging. We passen dit hier aan.
        benodigde_prijsscore = r["Totaal"] - (eigen_kwaliteit * (weging_kwaliteit/100))  # Vereist minimaal om te winnen
        if benodigde_prijsscore < 0:
            benodigde_prijsscore = 0
        # Omrekenen naar procentueel verschil t.o.v. max_punten_prijs (bijv. 400):\n
        perc_verschil = ((benodigde_prijsscore) / max_punten_prijs) * 100
        prijsscore_overzicht.append(f"{r['Naam']}: Je hebt minimaal een prijsscore van {benodigde_prijsscore:.2f} nodig, dit is ongeveer {perc_verschil:.1f}% van de maximale prijsscore.")
    
    for s in prijsscore_overzicht:
        st.write("- " + s)
    
    st.markdown("### Eigen ingevulde scores")
    st.write(f"Jouw inschrijvingsprijs: {eigen_prijs:.2f} euro")
    st.write(f"Kwaliteitsscore (totaal): {eigen_kwaliteit:.2f}")
    st.write(f"Prijsscore: {eigen_prijsscore:.2f}")
    st.write(f"**Eindtotaal: {eigen_totaal:.2f}**")
    
    st.markdown("---")
    st.caption("Tip: maak een screenshot of exporteer de pagina voor archivering.")

else:
    st.info("Klik op 'Analyseer' om de resultaten te berekenen.")

