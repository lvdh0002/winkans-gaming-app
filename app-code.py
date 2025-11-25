
import streamlit as st
import pandas as pd
import math
import io
import os

st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

# CSS
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

PRIMARY_COLOR="#7A1F1F"
LOGO_PATH=os.path.join("assets","logo_jde.png")

if os.path.exists(LOGO_PATH): st.image(LOGO_PATH,width=120)
st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>",unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
kwaliteit_pct=st.sidebar.number_input("Kwaliteit (%)",0,100,60,1)
prijs_pct=st.sidebar.number_input("Prijs (%)",0,100,40,1)

scales={"0-2-4-6-8-10":[0,2,4,6,8,10],"0-2,5-5-7,5-10":[0,2.5,5,7.5,10],"0%-20%-40%-60%-80%-100%":[0,20,40,60,80,100],"0-25-50-75-100":[0,25,50,75,100],"Custom...":None}
scale_label=st.sidebar.selectbox("Kies een schaal",list(scales.keys()))
scale_values=scales[scale_label] if scale_label!="Custom..." else [float(x) for x in st.sidebar.text_input("Eigen schaal","0,25,50,75,100").split(",")]
max_scale=max(scale_values)
criteria=[c.strip() for c in st.sidebar.text_input("Criterianamen","Kwaliteit,Service").split(",") if c.strip()]
max_points_criteria={c:st.sidebar.number_input(f"Max punten {c}",1,200,30) for c in criteria}
max_price_points=st.sidebar.number_input("Max punten Prijs",1,200,40)
verwachte_scores_eigen={c:float(st.sidebar.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_eigen_{c}")) for c in criteria}
margin_pct=st.sidebar.number_input("% duurder dan goedkoopste (eigen)",0.0,100.0,10.0,0.1)

st.header("📥 Concurrentsituaties")
num_scen=st.number_input("Aantal situaties",1,15,3)
scenarios=[]
for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}"):
        naam=st.text_input("Naam concurrent",f"Concurrent {i+1}",key=f"naam{i}")
        is_cheapest=st.checkbox("Is goedkoopste?",key=f"cheap{i}")
        pct=st.number_input("% duurder dan goedkoopste (conc.)",0.0,100.0,margin_pct,0.1,key=f"pct{i}") if not is_cheapest else 0.0
        kval_scores={c:float(st.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam":naam,"pct":pct,"kval_scores":kval_scores})

# Functions
def score_to_points(s,maxp): return (float(s)/max_scale)*maxp
def compute_quality_points(scores): return sum(score_to_points(scores[c],max_points_criteria[c]) for c in criteria)
def absolute_price_points(marge,M): return M*(1-marge/100)

def simulate_drop_for_win(my_margin,comp_margin,jde_quality,comp_quality,M):
    current=my_margin
    while current>=-20:  # tot 20% goedkoper
        # herbereken relatieve marges
        cheapest=current if current<comp_margin else comp_margin
        my_rel=max(0,current-cheapest)
        comp_rel=max(0,comp_margin-cheapest)
        my_price=M*(1-my_rel/100)
        comp_price=M*(1-comp_rel/100)
        if jde_quality+my_price>comp_quality+comp_price:
            drop=my_margin-current
            return int(math.ceil(drop)),int(round(current))
        current-=0.1
    return None,None

# Analyse
st.header("Resultaten")
if st.button("Bereken winkansen"):
    jde_quality_pts=compute_quality_points(verwachte_scores_eigen)
    jde_price=absolute_price_points(margin_pct,max_price_points)
    overzicht=[]
    for idx,s in enumerate(scenarios,start=1):
        comp_margin=float(s["pct"])
        comp_quality_pts=compute_quality_points(s["kval_scores"])
        comp_price=absolute_price_points(comp_margin,max_price_points)
        my_total=jde_quality_pts+jde_price; comp_total=comp_quality_pts+comp_price
        status="WIN" if my_total>comp_total else "LOSE" if my_total<comp_total else "DRAW"
        verschil=int(round(my_total-comp_total))
        drop_int,target_margin=simulate_drop_for_win(margin_pct,comp_margin,jde_quality_pts,comp_quality_pts,max_price_points)
        prijsactie="Geen actie mogelijk" if drop_int is None else f"Verlaag {drop_int}%-punt (naar {target_margin}%)"
        overzicht.append({"Scenario":f"{idx}. {s['naam']}","Status":status,"JDE prijs":int(round(jde_price)),"JDE kwaliteit":int(round(jde_quality_pts)),"JDE totaal":int(round(my_total)),"Conc prijs":int(round(comp_price)),"Conc kwaliteit":int(round(comp_quality_pts)),"Conc totaal":int(round(comp_total)),"Verschil":verschil,"Prijsactie":prijsactie})
    df=pd.DataFrame(overzicht,columns=["Scenario","Status","JDE prijs","JDE kwaliteit","JDE totaal","Conc prijs","Conc kwaliteit","Conc totaal","Verschil","Prijsactie"])
    st.dataframe(df,use_container_width=True)
    st.download_button("Download CSV",df.to_csv(index=False),"winkans_overzicht.csv","text/csv")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
