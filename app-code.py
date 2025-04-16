import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Tender Analyse Tool", layout="wide")

st.title("📊 Tender Analyse Tool")

st.sidebar.header("🔧 Instellingen")

# Aantal kwaliteitscriteria kiezen
num_criteria = st.sidebar.selectbox("Aantal kwaliteitscriteria", options=[2, 3, 4, 5], index=3)

criteria_labels = [f"W{i+1}" for i in range(num_criteria)]

# Weging invullen
st.sidebar.subheader("Wegingen")
kwaliteitswegingen = {}
total_k = 0
for label in criteria_labels:
    w = st.sidebar.number_input(f"Weging {label} (%)", min_value=0, max_value=100, value=20, step=1)
    kwaliteitswegingen[label] = w
    total_k += w

prijsweging = st.sidebar.number_input("Weging prijs (%)", min_value=0, max_value=100, value=100-total_k, step=1)

# Beoordelingsschaal kiezen
st.sidebar.subheader("Beoordelingsschaal kwaliteit")
schaal_optie = st.sidebar.selectbox(
    "Type beoordelingsschaal",
    ["Percentage (0-25-50-75-100)", "Percentage (20-40-60-80-100)", "Punten (2-4-6-8-10)"]
)

if schaal_optie == "Percentage (0-25-50-75-100)":
    schaal = {"Slecht": 0, "Matig": 25, "Voldoende": 50, "Goed": 75, "Uitstekend": 100}
elif schaal_optie == "Percentage (20-40-60-80-100)":
    schaal = {"Slecht": 20, "Matig": 40, "Voldoende": 60, "Goed": 80, "Uitstekend": 100}
else:
    schaal = {"Slecht": 2, "Matig": 4, "Voldoende": 6, "Goed": 8, "Uitstekend": 10}

st.markdown("---")
st.subheader("📥 Scenario invoer")

st.markdown("Vul hieronder de scores in van verschillende inschrijvers. Gebruik de woorden uit de beoordelingsschaal of cijfers.")

num_inschrijvers = st.number_input("Aantal inschrijvers", min_value=2, max_value=10, value=3)

cols = ["Inschrijver", "Prijs"] + criteria_labels

rows = []
for i in range(num_inschrijvers):
    with st.expander(f"Inschrijver {chr(65+i)}"):
        naam = st.text_input(f"Naam inschrijver {chr(65+i)}", value=f"Inschrijver {chr(65+i)}")
        prijs = st.number_input(f"Prijs (in euro's)", min_value=0.0, value=100000.0, key=f"prijs_{i}")
        scores = []
        for c in criteria_labels:
            s = st.selectbox(f"Score {c}", options=list(schaal.keys()), key=f"score_{i}_{c}")
            scores.append(s)
        rows.append([naam, prijs] + scores)

# Verwerking
st.markdown("---")
st.subheader("📈 Resultaten")

if st.button("Analyseer"):
    df = pd.DataFrame(rows, columns=cols)

    # Scores omzetten
    for c in criteria_labels:
        df[c + "_score"] = df[c].map(schaal)

    # Normale kwaliteitsscore berekening
    for c in criteria_labels:
        df[c + "_gewogen"] = df[c + "_score"] * kwaliteitswegingen[c] / 100

    df["Totaal kwaliteit"] = df[[c + "_gewogen" for c in criteria_labels]].sum(axis=1)

    # Prijsscore berekening
    min_prijs = df["Prijs"].min()
    df["Prijsscore"] = df["Prijs"].apply(lambda x: (min_prijs / x) * prijsweging)

    df["Eindtotaal"] = df["Totaal kwaliteit"] + df["Prijsscore"]

    df_sorted = df.sort_values(by="Eindtotaal", ascending=False).reset_index(drop=True)
    df_sorted.index += 1

    st.dataframe(df_sorted[["Inschrijver", "Prijs", "Totaal kwaliteit", "Prijsscore", "Eindtotaal"]], use_container_width=True)

    winnaar = df_sorted.iloc[0]
    st.success(f"🏆 De winnende inschrijver is: {winnaar['Inschrijver']} met {winnaar['Eindtotaal']:.2f} punten")

else:
    st.info("Klik op 'Analyseer' om de resultaten te berekenen.")
