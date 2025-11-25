
import streamlit as st
import pandas as pd
import numpy as np
import io
import os

# --- Imports ---
HAS_MPL = True
try:
    import matplotlib.pyplot as plt
except:
    HAS_MPL = False

HAS_RL = True
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except:
    HAS_RL = False

# --- Page Config ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")

# --- CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');
h1, h2, h3, h4 { font-family: 'Oswald', sans-serif !important; font-weight:700; color:#7A1F1F; }
html, body, .stApp { background-color:#F3E9DB; font-family:'Segoe UI','Aptos',sans-serif; }
.stButton>button { font-family:'Oswald',sans-serif;font-weight:700;background:#7A1F1F;color:#fff;border-radius:6px; }
.stButton>button:hover { background:#4B2E2B; }
thead tr th { background:#C8A165 !important;color:#fff !important; }
</style>
""", unsafe_allow_html=True)

# --- Huisstijl kleuren ---
PRIMARY_COLOR="#7A1F1F"; ACCENT_GOLD="#C8A165"; QUALITY_COLOR="#2E7D32"; PRICE_COLOR="#1565C0"
LOGO_PATH=os.path.join("assets","logo_jde.png")

# --- Titel ---
if os.path.exists(LOGO_PATH): st.image(LOGO_PATH,width=120)
st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>",unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
def _sync_from_quality(): st.session_state.price_input=max(0,100-st.session_state.quality_input)
def _sync_from_price(): st.session_state.quality_input=max(0,100-st.session_state.price_input)
col1,col2=st.sidebar.columns(2)
with col1: st.number_input("Kwaliteit (%)",0,100,60,1,key="quality_input",on_change=_sync_from_quality)
with col2: st.number_input("Prijs (%)",0,100,40,1,key="price_input",on_change=_sync_from_price)
kwaliteit_pct=st.session_state.quality_input; prijs_pct=st.session_state.price_input

# --- Puntenschaal ---
scales={"0-2-4-6-8-10":[0,2,4,6,8,10],"0-2,5-5-7,5-10":[0,2.5,5,7.5,10],"0%-20%-40%-60%-80%-100%":[0,20,40,60,80,100],"0-25-50-75-100":[0,25,50,75,100],"Custom...":None}
scale_label=st.sidebar.selectbox("Kies een schaal",list(scales.keys()))
scale_values=scales[scale_label] if scale_label!="Custom..." else [float(x) for x in st.sidebar.text_input("Eigen schaal","0,25,50,75,100").split(",")]
max_scale=max(scale_values)
criteria=[c.strip() for c in st.sidebar.text_input("Criterianamen","Kwaliteit,Service").split(",") if c.strip()]
max_points_criteria={c:st.sidebar.number_input(f"Max punten {c}",1,200,30) for c in criteria}
max_price_points=st.sidebar.number_input("Max punten Prijs",1,200,40)
verwachte_scores_eigen={c:float(st.sidebar.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_eigen_{c}")) for c in criteria}
margin_pct=st.sidebar.number_input("% duurder dan goedkoopste (eigen)",0.0,100.0,10.0,0.1)

# --- Scenario invoer ---
st.header("📥 Concurrentsituaties")
num_scen=st.number_input("Aantal situaties",1,15,3)
scenarios=[]
for i in range(int(num_scen)):
    with st.expander(f"Situatie {i+1}"):
        naam=st.text_input("Naam concurrent",f"Concurrent {i+1}",key=f"naam{i}")
        is_cheapest=st.checkbox("Is goedkoopste?",key=f"cheap{i}")
        pct=st.number_input("% duurder dan goedkoopste",0.0,100.0,margin_pct,0.1,key=f"pct{i}") if not is_cheapest else 0.0
        kval_scores={c:float(st.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam":naam,"pct":pct,"kval_scores":kval_scores})

# --- Helper functies ---
def score_to_points(s,maxp): return (float(s)/max_scale)*maxp
def compute_quality_points(scores): return sum(score_to_points(scores[c],max_points_criteria[c]) for c in criteria)

def compute_totals(jde_margin,comp_margins,jde_quality,comp_quality):
    cheapest=min([jde_margin]+comp_margins)
    jde_price=max_price_points*(1-(jde_margin-cheapest)/100)
    comp_prices=[max_price_points*(1-(m-cheapest)/100) for m in comp_margins]
    return jde_price,comp_prices

def find_min_margin_for_win(jde_quality,comp_quality,comp_margin,start_margin):
    cheapest=min(start_margin,comp_margin)
    for m in np.arange(start_margin,-0.1,-0.1):
        jde_price=max_price_points*(1-(m-cheapest)/100)
        comp_price=max_price_points*(1-(comp_margin-cheapest)/100)
        if jde_quality+jde_price>comp_quality+comp_price: return m,round(start_margin-m,1)
    return 0.0,round(start_margin,1)

def best_quality_step(scores):
    best=None
    for c in criteria:
        cur=scores[c]
        for nxt in [x for x in scale_values if x>cur]:
            gain=score_to_points(nxt,max_points_criteria[c])-score_to_points(cur,max_points_criteria[c])
            if best is None or gain>best[3]: best=(c,cur,nxt,gain)
    return best

# --- Analyse ---
st.header("Resultaten")
if st.button("Bereken winkansen"):
    jde_quality=compute_quality_points(verwachte_scores_eigen)
    comp_margins=[s["pct"] for s in scenarios]
    jde_price,_=compute_totals(margin_pct,comp_margins,jde_quality,[compute_quality_points(s["kval_scores"]) for s in scenarios])
    overzicht=[]
    for s in scenarios:
        comp_quality=compute_quality_points(s["kval_scores"])
        comp_margin=s["pct"]
        jde_price,comp_prices=compute_totals(margin_pct,[comp_margin],jde_quality,[comp_quality])
        comp_price=comp_prices[0]
        jde_total=jde_quality+jde_price; comp_total=comp_quality+comp_price
        status="WIN" if jde_total>comp_total else "LOSE" if jde_total<comp_total else "DRAW"
        verschil=jde_total-comp_total
        target_margin,drop=find_min_margin_for_win(jde_quality,comp_quality,comp_margin,margin_pct)
        prijsadvies=f"Verlaag {drop:.0f}%-punt (naar {target_margin:.0f}%)" if status!="WIN" else "Geen actie nodig"
        best_step=best_quality_step(verwachte_scores_eigen)
        kwaliteitsadvies=f"Verhoog {best_step[0]} van {best_step[1]:.0f}→{best_step[2]:.0f} (+{best_step[3]:.0f} ptn)" if best_step else "-"
        overzicht.append({"Scenario":s["naam"],"Status":status,"JDE totaal":f"{jde_total:.0f}","JDE prijs":f"{jde_price:.0f}","JDE kwaliteit":f"{jde_quality:.0f}","Concurrent totaal":f"{comp_total:.0f}","Conc prijs":f"{comp_price:.0f}","Conc kwaliteit":f"{comp_quality:.0f}","Verschil":f"{verschil:.0f}","% duurder":f"{margin_pct:.0f}%","Prijsactie":prijsadvies,"Kwaliteitsadvies":kwaliteitsadvies})
    df=pd.DataFrame(overzicht)

    # Kleurcodering
    def color_status(val):
        return "background-color:#81C784" if val=="WIN" else "background-color:#E57373" if val=="LOSE" else "background-color:#B0BEC5"
    st.dataframe(df.style.applymap(color_status,subset=["Status"]),use_container_width=True)

    # CSV-download
    st.download_button("Download CSV",df.to_csv(index=False),"winkans_overzicht.csv")

    # PDF-download
    if HAS_RL:
        buf=io.BytesIO()
        doc=SimpleDocTemplate(buf,pagesize=A4)
        styles=getSampleStyleSheet()
        styles.add(ParagraphStyle(name="JDETitle",parent=styles["Title"],textColor=colors.HexColor(PRIMARY_COLOR)))
        flow=[]
        if os.path.exists(LOGO_PATH): flow.append(Image(LOGO_PATH,width=100,height=48))
        flow.append(Paragraph("Advies: Winkans & Acties (BPKV)",styles["JDETitle"]))
        flow.append(Spacer(1,12))
        table_data=[list(df.columns)]+df.values.tolist()
        t=Table(table_data)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(ACCENT_GOLD)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey)]))
        flow.append(t)
        doc.build(flow)
        buf.seek(0)
        st.download_button("📄 Download PDF (JDE-stijl)",buf,"advies_winkans.pdf","application/pdf")
    else:
        st.info("PDF niet beschikbaar (reportlab ontbreekt).")
else:
    st.info("Klik op 'Bereken winkansen' om te starten.")
