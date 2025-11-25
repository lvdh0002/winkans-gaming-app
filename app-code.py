
import streamlit as st
import pandas as pd
import math
import io
import os

# --- Page config & eenvoudige JDE-stijl ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');
h1,h2,h3,h4 {font-family:'Oswald',sans-serif!important;font-weight:700;color:#7A1F1F;}
html,body,.stApp {background-color:#F3E9DB;font-family:'Segoe UI','Aptos',sans-serif!important;color:#000;}
.stButton>button {font-family:'Oswald',sans-serif!important;font-weight:700;background:#7A1F1F;color:#fff;border-radius:6px;}
.stButton>button:hover {background:#4B2E2B;}
thead tr th {background:#C8A165!important;color:#fff!important;}
[data-testid="stSidebar"]>div:first-child {background:linear-gradient(180deg,#7A1F1F 0%,#4B2E2B 100%);color:#fff;}
[data-testid="stSidebar"] label {color:#fff!important;}
</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR = "#7A1F1F"
LOGO_PATH = os.path.join("assets","logo_jde.png")
if os.path.exists(LOGO_PATH): st.image(LOGO_PATH,width=120)
st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# --- Sidebar: methodiek & invoer ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
# Wegingen (bijv. 60/40)
kwaliteit_pct = st.sidebar.number_input("Kwaliteit (%)", 0, 100, 60, 1)
prijs_pct     = st.sidebar.number_input("Prijs (%)",     0, 100, 40, 1)

# Puntenschaal & criteria
scales = {
    "0-2-4-6-8-10": [0,2,4,6,8,10],
    "0-2,5-5-7,5-10": [0,2.5,5,7.5,10],
    "0%-20%-40%-60%-80%-100%": [0,20,40,60,80,100],
    "0-25-50-75-100": [0,25,50,75,100],
    "Custom...": None
}
scale_label = st.sidebar.selectbox("Kies een schaal", list(scales.keys()))
scale_values = scales[scale_label] if scale_label!="Custom..." else [
    float(x) for x in st.sidebar.text_input("Eigen schaal","0,25,50,75,100").split(",")
]
max_scale = max(scale_values)

criteria_raw = st.sidebar.text_input("Criterianamen (komma, min 2)", "Kwaliteit,Service")
criteria = [c.strip() for c in criteria_raw.split(",") if c.strip()]
max_points_criteria = {c: st.sidebar.number_input(f"Max punten {c}", 1, 200, 30) for c in criteria}
max_price_points    = st.sidebar.number_input("Max punten Prijs",    1, 200, 40)

# JDE-scores & marge
st.sidebar.header("Stap 2: JDE inschatting")
verwachte_scores_eigen = {
    c: float(st.sidebar.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_eigen_{c}"))
    for c in criteria
}
margin_pct = st.sidebar.number_input("% duurder dan goedkoopste (JDE)", 0.0, 100.0, 10.0, 0.1)

# --- Scenarios ---
st.header("📥 Concurrentsituaties")
num_scen = st.number_input("Aantal situaties", 1, 15, 3)
scenarios = []
for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}"):
        naam        = st.text_input("Naam concurrent", f"Concurrent {i+1}", key=f"naam{i}")
        is_cheapest = st.checkbox("Concurrent is goedkoopste?", key=f"cheap{i}")  # bepaalt of marge=0%
        comp_marge  = 0.0 if is_cheapest else st.number_input("% duurder dan goedkoopste (conc.)", 0.0, 100.0, margin_pct, 0.1, key=f"pct{i}")
        kval_scores = {c: float(st.selectbox(f"Score {c}", [str(x) for x in scale_values], key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam": naam, "marge": float(comp_marge), "is_cheapest": is_cheapest, "kval_scores": kval_scores})

# --- Helpers ---
def score_to_points(s, maxp):
    """Normaliseer een criteriumscore s (tegen max_scale) naar maxp punten."""
    return (float(s)/max_scale) * maxp

def compute_quality_points(scores_dict):
    """Som van kwaliteitspunten over alle criteria."""
    return sum(score_to_points(scores_dict[c], max_points_criteria[c]) for c in criteria)

def absolute_price_points(marge, M):
    """Steady prijspunten: max(M) bij marge 0%; lineair naar beneden bij hogere marges."""
    return M * (1 - marge/100.0)

def required_drop_piecewise(my_margin, comp_margin, Qm, Qc, M):
    """
    Gesloten-formule voor minimale JDE-marge m_req om te winnen tegen één concurrent.
    - Regime A (jij blijft duurder): m_req_A = c + (100/M)*(Qm - Qc), alleen geldig als m_req_A >= c
    - Regime B (jij wordt goedkoopste): m_req_B = c - (100/M)*(Qc - Qm)
    Neem de variant die bij het regime hoort. Return (m_req, drop, target_margin_int).
    """
    # Kandidaten
    m_req_A = comp_margin + (100.0/M) * (Qm - Qc)
    m_req_B = comp_margin - (100.0/M) * (Qc - Qm)

    # Kies regime-consistente m_req
    if m_req_A >= comp_margin:
        m_req = m_req_A   # je kunt winnen zonder onder de goedkoopste te gaan
    else:
        m_req = m_req_B   # je moet onder de goedkoopste gaan (relatieve herweging)

    drop = max(0.0, my_margin - m_req)
    drop_int = int(math.ceil(drop))  # naar boven afronden
    target_int = int(round(my_margin - drop_int))
    return m_req, drop_int, target_int

# --- Analyse & Output ---
st.header("Resultaten")

if st.button("Bereken winkansen"):
    # JDE kwaliteit & prijs (steady weergave)
    jde_quality_pts = compute_quality_points(verwachte_scores_eigen)
    jde_price_pts   = absolute_price_points(margin_pct, max_price_points)
    jde_total       = jde_quality_pts + jde_price_pts

    rows = []
    for idx, s in enumerate(scenarios, start=1):
        comp_margin      = s["marge"]
        comp_quality_pts = compute_quality_points(s["kval_scores"])
        comp_price_pts   = absolute_price_points(comp_margin, max_price_points)
        comp_total       = comp_quality_pts + comp_price_pts

        status  = "WIN" if jde_total > comp_total else ("LOSE" if jde_total < comp_total else "DRAW")
        verschil = int(round(jde_total - comp_total))

        # Prijsactie: minimale objectieve zakking (met relatieve herweging zodra JDE goedkoper wordt)
        m_req, drop_int, target_int = required_drop_piecewise(margin_pct, comp_margin, jde_quality_pts, comp_quality_pts, max_price_points)
        prijsactie = "Geen actie nodig" if (status=="WIN" or drop_int<=0) else f"Verlaag {drop_int}% (naar {target_int}%)"

        # Kwaliteitsactie (zonder prijsverlaging): kleinste stap die direct WIN oplevert; anders beste stap
        # We toetsen op gelijkblijvende marges (dus steady prijspunten), puur kwaliteit.
        qual_step = None
        for c in criteria:
            cur = float(verwachte_scores_eigen[c])
            higher = [x for x in scale_values if float(x) > cur]
            for nxt in higher:
                gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                if (jde_quality_pts + gain + jde_price_pts) > comp_total + 0.005:  # WIN met kwaliteit alleen
                    qual_step = (c, cur, float(nxt), float(gain))
                    break
            if qual_step: break

        if qual_step:
            c, cur, nxt, gain = qual_step
            kwaliteitsactie = f"Verhoog {c} van {int(round(cur))}→{int(round(nxt))} (+{int(round(gain))} ptn)"
        else:
            # anders toon beste stap (max puntenwinst), nog steeds 'objectief' (geen oordeel over haalbaarheid)
            best = None
            for c in criteria:
                cur = float(verwachte_scores_eigen[c])
                higher = [x for x in scale_values if float(x) > cur]
                for nxt in higher:
                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                    if (best is None) or (gain > best[3]):
                        best = (c, cur, float(nxt), float(gain))
            kwaliteitsactie = f"Beste stap: {best[0]} {int(round(best[1]))}→{int(round(best[2]))} (+{int(round(best[3]))} ptn)" if best else "-"

        rows.append({
            "Scenario": f"{idx}. {s['naam']}",
            "Status": status,
            # JDE eerst (prijs/kwaliteit/totaal), dan concurrent (idem), dan verschil & acties
            "JDE prijs":         int(round(jde_price_pts)),
            "JDE kwaliteit":     int(round(jde_quality_pts)),
            "JDE totaal":        int(round(jde_total)),
            "Conc prijs":        int(round(comp_price_pts)),
            "Conc kwaliteit":    int(round(comp_quality_pts)),
            "Conc totaal":       int(round(comp_total)),
            "Verschil":          verschil,
            "Prijsactie":        prijsactie,
            "Kwaliteitsactie":   kwaliteitsactie
        })

    # Tabel in intuïtieve volgorde
    df = pd.DataFrame(rows, columns=[
        "Scenario","Status",
        "JDE prijs","JDE kwaliteit","JDE totaal",
        "Conc prijs","Conc kwaliteit","Conc totaal",
        "Verschil","Prijsactie","Kwaliteitsactie"
    ])

    # Laat index starten bij 1
    df.index = pd.RangeIndex(start=1, stop=len(df)+1, step=1)
    df.index.name = ""  # geen label boven index

    st.dataframe(df, use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False), "winkans_overzicht.csv", "text/csv")

else:
    st.info("Klik op 'Bereken winkansen' om te starten.")

