
import streamlit as st
import pandas as pd
import numpy as np
import math
import io
import os

HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except:
    HAS_MPL = False

HAS_RL = True
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except:
    HAS_RL = False

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

PRIMARY_COLOR="#7A1F1F"; ACCENT_GOLD="#C8A165"
LOGO_PATH=os.path.join("assets","logo_jde.png")

if os.path.exists(LOGO_PATH): st.image(LOGO_PATH,width=120)
st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>",unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
def _sync_from_quality(): st.session_state.price_input=max(0,100-st.session_state.quality_input)
def _sync_from_price(): st.session_state.quality_input=max(0,100-st.session_state.price_input)
col1,col2=st.sidebar.columns(2)
with col1: st.number_input("Kwaliteit (%)",0,100,60,1,key="quality_input",on_change=_sync_from_quality)
with col2: st.number_input("Prijs (%)",0,100,40,1,key="price_input",on_change=_sync_from_price)
kwaliteit_pct=st.session_state.quality_input; prijs_pct=st.session_state.price_input

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
    with st.expander(f"Situatie {i+1}"):
        naam=st.text_input("Naam concurrent",f"Concurrent {i+1}",key=f"naam{i}")
        is_cheapest=st.checkbox("Is goedkoopste?",key=f"cheap{i}")
        pct=st.number_input("% duurder dan goedkoopste (conc.)",0.0,100.0,margin_pct,0.1,key=f"pct{i}") if not is_cheapest else 0.0
        kval_scores={c:float(st.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam":naam,"pct":pct,"kval_scores":kval_scores})

# Functions
def score_to_points(s,maxp): return (float(s)/max_scale)*maxp
def compute_quality_points(scores): return sum(score_to_points(scores[c],max_points_criteria[c]) for c in criteria)
def price_points_from_margins(my_margin,comp_margin,M):
    cheapest=min(my_margin,comp_margin)
    my_rel=max(0,my_margin-cheapest); comp_rel=max(0,comp_margin-cheapest)
    return M*(1-my_rel/100),M*(1-comp_rel/100)

def simulate_drop_for_win(my_margin,comp_margin,jde_quality,comp_quality,M):
    current=my_margin
    while current>=0:
        my_price,comp_price=price_points_from_margins(current,comp_margin,M)
        if jde_quality+my_price>comp_quality+comp_price:
            drop=my_margin-current
            return int(math.ceil(drop)),int(round(current))
        current-=0.1
    return None,None

def dashboard_figure(rows):
    if not HAS_MPL: return None
    MOS_GREEN="#6B8E23"; BROWN="#8B5E3C"; LIGHT_GREEN="#A9BA9D"; BEIGE="#C4A484"
    n=len(rows)
    fig,ax=plt.subplots(figsize=(5,0.3*n+1))  # compacter
    y_you=np.arange(n)*2; y_comp=y_you+0.8
    for i,r in enumerate(rows):
        ax.barh(y_you[i],r["you_quality"],color=MOS_GREEN,label="Kwaliteit (Jij)" if i==0 else None)
        ax.barh(y_you[i],r["you_price"],left=r["you_quality"],color=BROWN,label="Prijs (Jij)" if i==0 else None)
        ax.barh(y_comp[i],r["comp_quality"],color=LIGHT_GREEN,label="Kwaliteit (Conc)" if i==0 else None)
        ax.barh(y_comp[i],r["comp_price"],left=r["comp_quality"],color=BEIGE,label="Prijs (Conc)" if i==0 else None)
        you_tot=int(round(r["you_quality"]+r["you_price"]))
        comp_tot=int(round(r["comp_quality"]+r["comp_price"]))
        ax.text(you_tot+0.3,y_you[i],f"{you_tot}",va="center",color=PRIMARY_COLOR)
        ax.text(comp_tot+0.3,y_comp[i],f"{comp_tot}",va="center",color=PRIMARY_COLOR)
        ax.text(0,y_comp[i],r["naam"],va="center",ha="left",color=PRIMARY_COLOR,fontweight="bold")
    ax.set_yticks([]); ax.set_xlabel("Punten",color=PRIMARY_COLOR)
    ax.set_title("Dashboard: overzicht per scenario",color=PRIMARY_COLOR,fontweight="bold")
    ax.grid(axis="x",alpha=0.25); ax.legend(loc="upper right")
    st.pyplot(fig); return fig

# Analyse
st.header("Resultaten")
if st.button("Bereken winkansen"):
    jde_quality_pts=compute_quality_points(verwachte_scores_eigen)
    overzicht=[]; dashboard=[]
    for s in scenarios:
        comp_margin=float(s["pct"]); comp_quality_pts=compute_quality_points(s["kval_scores"])
        my_price_now,comp_price_now=price_points_from_margins(margin_pct,comp_margin,max_price_points)
        my_total=jde_quality_pts+my_price_now; comp_total=comp_quality_pts+comp_price_now
        status="WIN" if my_total>comp_total else "LOSE" if my_total<comp_total else "DRAW"
        verschil=int(round(my_total-comp_total))
        drop_int,target_margin=simulate_drop_for_win(margin_pct,comp_margin,jde_quality_pts,comp_quality_pts,max_price_points)
        prijsactie="Geen actie nodig" if status=="WIN" or drop_int is None else f"Verlaag {drop_int}%-punt (naar {target_margin}%)"
        overzicht.append({"Scenario":s["naam"],"Status":status,"JDE totaal":int(round(my_total)),"JDE prijs":int(round(my_price_now)),"JDE kwaliteit":int(round(jde_quality_pts)),"Concurrent totaal":int(round(comp_total)),"Conc prijs":int(round(comp_price_now)),"Conc kwaliteit":int(round(comp_quality_pts)),"Verschil":verschil,"Prijsactie":prijsactie})
        dashboard.append({"naam":s["naam"],"you_quality":jde_quality_pts,"you_price":my_price_now,"comp_quality":comp_quality_pts,"comp_price":comp_price_now})
    df=pd.DataFrame(overzicht)
    st.dataframe(df,use_container_width=True)
    st.download_button("Download CSV",df.to_csv(index=False),"winkans_overzicht.csv","text/csv")
    st.subheader("📊 Dashboard-grafiek")
    dashboard_figure(dashboard)
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
