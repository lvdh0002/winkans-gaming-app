
import streamlit as st
import pandas as pd
import math
import io
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

# --- Page config & JDE-stijl ---
st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap');
h1,h2,h3,h4 {font-family:'Oswald',sans-serif!important;font-weight:700;color:#7A1F1F;}
html,body,.stApp {background-color:#F3E9DB;font-family:'Segoe UI','Aptos',sans-serif!important;color:#000;}
.stButton>button {font-family:'Oswald',sans-serif!important;font-weight:700;background:#7A1F1F;color:#fff;border-radius:6px;}
.stButton>button:hover {background:#4B2E2B;}
thead tr th {background:#C8A165!important;color:#fff!important;}
[data-testid="stSidebar"]>div:first-child {background:#A13D3B!important;color:#fff;}
[data-testid="stSidebar"] label {color:#fff!important;}
</style>
""", unsafe_allow_html=True)

PRIMARY_COLOR="#7A1F1F"; ACCENT_GOLD="#C8A165"
PAGE_BEIGE="#F3E9DB"
WIN_ROW_BG=colors.HexColor("#E6EBD8")
LOSE_ROW_BG=colors.HexColor("#EAD5D1")
DRAW_ROW_BG=colors.HexColor("#EDE1C9")
LOGO_PATH=os.path.join("assets","logo_jde.png")

if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=120)
st.markdown("<h1>Tool om winkansen te berekenen o.b.v. BPKV</h1>", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.header("Stap 1: Beoordelingsmethodiek")
kwaliteit_pct=st.sidebar.number_input("Kwaliteit (%)",0,100,60,1)
prijs_pct=st.sidebar.number_input("Prijs (%)",0,100,40,1)

scales={"0-2-4-6-8-10":[0,2,4,6,8,10],"0-2,5-5-7,5-10":[0,2.5,5,7.5,10],"0%-20%-40%-60%-80%-100%":[0,20,40,60,80,100],"0-25-50-75-100":[0,25,50,75,100],"Custom...":None}
scale_label=st.sidebar.selectbox("Kies een schaal",list(scales.keys()))
scale_values=scales[scale_label] if scale_label!="Custom..." else [float(x) for x in st.sidebar.text_input("Eigen schaal","0,25,50,75,100").split(",")]
max_scale=max(scale_values)
criteria=[c.strip() for c in st.sidebar.text_input("Criterianamen","Duurzaamheid,Service").split(",") if c.strip()]
max_points_criteria={c:st.sidebar.number_input(f"Max punten {c}",1,200,30) for c in criteria}
max_price_points=st.sidebar.number_input("Max punten Prijs",1,200,40)
verwachte_scores_eigen={c:float(st.sidebar.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_eigen_{c}")) for c in criteria}
margin_pct=st.sidebar.number_input("% duurder dan goedkoopste (JDE)",0.0,100.0,10.0,0.1)

st.header("📥 Concurrentsituaties")
num_scen=st.number_input("Aantal situaties",1,15,3)
scenarios=[]
for i in range(int(num_scen)):
    with st.expander(f"Scenario {i+1}"):
        naam=st.text_input("Naam concurrent",f"Concurrent {i+1}",key=f"naam{i}")
        is_cheapest=st.checkbox("Concurrent is goedkoopste?",key=f"cheap{i}")
        pct=0.0 if is_cheapest else st.number_input("% duurder dan goedkoopste (conc.)",0.0,100.0,margin_pct,0.1,key=f"pct{i}")
        kval_scores={c:float(st.selectbox(f"Score {c}",[str(x) for x in scale_values],key=f"score_{i}_{c}")) for c in criteria}
        scenarios.append({"naam":naam,"marge":pct,"kval_scores":kval_scores})

# --- Helpers ---
def score_to_points(s,maxp): return (float(s)/max_scale)*maxp
def compute_quality_points(scores): return sum(score_to_points(scores[c],max_points_criteria[c]) for c in criteria)
def absolute_price_points(marge,M): return M*(1-marge/100)
def required_drop_piecewise(my_margin,comp_margin,Qm,Qc,M):
    m_req_A = comp_margin + (100.0/M)*(Qm - Qc)
    m_req_B = comp_margin - (100.0/M)*(Qc - Qm)
    m_req   = m_req_A if m_req_A >= comp_margin else m_req_B
    drop    = max(0, my_margin - m_req)
    drop_int   = int(math.ceil(drop))
    target_int = int(round(my_margin - drop_int))
    return drop_int, target_int
def points_per_step_for_criterion(c):
    diffs = [scale_values[i+1]-scale_values[i] for i in range(len(scale_values)-1)]
    step_size = min([d for d in diffs if d > 0]) if diffs else 1
    return (max_points_criteria[c] / max_scale) * step_size
def advice_route_text(price_action, qual_action):
    p_needed = ("Verlaag" in price_action) and ("Geen actie nodig" not in price_action)
    q_needed = (qual_action not in ["-", "Ontoereikend", ""]) and ("Verhoog" in qual_action)
    if p_needed and q_needed: return "Adviesroute: prijs + kwaliteit"
    if p_needed and not q_needed: return "Adviesroute: prijs"
    if (not p_needed) and q_needed: return "Adviesroute: kwaliteit"
    return "Adviesroute: geen actie"

# --- Analyse ---
st.header("Resultaten")
if st.button("Bereken winkansen"):
    jde_quality_pts=compute_quality_points(verwachte_scores_eigen)
    jde_price_pts=absolute_price_points(margin_pct,max_price_points)
    jde_total=jde_quality_pts+jde_price_pts

    rows=[]
    win_no_action=0
    win_price=0
    win_quality=0
    global_drops=[]

    for idx,s in enumerate(scenarios,start=1):
        comp_margin=s["marge"]
        comp_quality_pts=compute_quality_points(s["kval_scores"])
        comp_price_pts=absolute_price_points(comp_margin,max_price_points)
        comp_total=comp_quality_pts+comp_price_pts

        status="WIN" if jde_total>comp_total else ("LOSE" if jde_total<comp_total else "DRAW")
        verschil=int(round(jde_total-comp_total))

        drop_int,target_int=required_drop_piecewise(margin_pct,comp_margin,jde_quality_pts,comp_quality_pts,max_price_points)
        if status == "DRAW" and drop_int == 0:
            drop_int  = 1
            target_int = int(round(margin_pct - 1))
        prijsactie = "Geen actie nodig" if status=="WIN" else f"Verlaag {drop_int}% (naar {target_int}%)"
        if status!="WIN" and drop_int>0:
            win_price += 1
            global_drops.append(drop_int)
        elif status=="WIN":
            win_no_action += 1

        qual_action = "-"
        if status!="WIN":
            found = False
            for c in criteria:
                cur = float(verwachte_scores_eigen[c])
                higher = [x for x in scale_values if float(x) > cur]
                for nxt in higher:
                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(cur, max_points_criteria[c])
                    if (jde_quality_pts + gain + jde_price_pts) > (comp_total + 0.005):
                        qual_action = f"Verhoog {c} {int(round(cur))}→{int(round(nxt))} (+{int(round(gain))} ptn)"
                        win_quality += 1
                        found = True
                        break
                if found: break
            if not found:
                qual_action = "Ontoereikend"

        rows.append({
            "Scenario": f"{idx}. {s['naam']}",
            "Status": status,
            "Verschil": verschil,
            "JDE totaal": int(round(jde_total)),
            "Conc totaal": int(round(comp_total)),
            "Prijsactie": prijsactie,
            "Kwaliteitsactie": qual_action
        })

    df=pd.DataFrame(rows)
    st.dataframe(df,use_container_width=True)

    # ---------- PDF Export ----------
    pdf_buf=io.BytesIO()
    doc=SimpleDocTemplate(pdf_buf,pagesize=landscape(A4),leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=24)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="JDETitle",fontName="Helvetica-Bold",fontSize=18,textColor=colors.HexColor(PRIMARY_COLOR)))
    styles.add(ParagraphStyle(name="JDENormal",fontName="Helvetica",fontSize=10,textColor=colors.black))
    styles.add(ParagraphStyle(name="JDEItalic",fontName="Helvetica-Oblique",fontSize=8,textColor=colors.HexColor("#333")))

    flow=[]
    if os.path.exists(LOGO_PATH): flow.append(Image(LOGO_PATH,width=100,height=40))  # behoud aspect ratio
    flow.append(Spacer(1,6))
    flow.append(Paragraph("Advies: Winkans & Acties (BPKV)",styles["JDETitle"]))
    flow.append(Spacer(1,10))

    # Overzicht JDE en scenario's
    jde_scores=", ".join([f"{c}: {int(verwachte_scores_eigen[c])}" for c in criteria])
    flow.append(Paragraph(f"<b>JDE uitgangspunt:</b> prijs {'goedkoopste' if margin_pct==0 else f'{margin_pct:.1f}% duurder'}, {jde_scores}",styles["JDENormal"]))
    for idx,s in enumerate(scenarios,start=1):
        comp_scores=", ".join([f"{c}: {int(s['kval_scores'][c])}" for c in criteria])
        flow.append(Paragraph(f"<b>Scenario {idx} ({s['naam']}):</b> prijs {'goedkoopste' if s['marge']==0 else f'{s['marge']:.1f}% duurder'}, {comp_scores}",styles["JDENormal"]))
    flow.append(Spacer(1,10))

    # Compacte tabel
    pdf_cols=["Scenario","Status","Verschil","JDE totaal","Conc totaal","Prijsactie","Kwaliteitsactie"]
    table_data=[pdf_cols]+df[pdf_cols].values.tolist()
    col_widths=[80,60,60,70,70,140,140]
    t=Table(table_data,colWidths=col_widths,repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor(ACCENT_GOLD)),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
    ]))
    for i in range(1,len(table_data)):
        status=str(table_data[i][1]).upper()
        bg=DRAW_ROW_BG
        if status=="WIN": bg=WIN_ROW_BG
        elif status=="LOSE": bg=LOSE_ROW_BG
        t.setStyle(TableStyle([('BACKGROUND',(0,i),(-1,i),bg)]))
    flow.append(t)
    flow.append(Spacer(1,10))

    # Adviesroute
    flow.append(Paragraph("Adviesroute per scenario:",styles["JDENormal"]))
    for i in range(len(df)):
        route=advice_route_text(df.iloc[i]["Prijsactie"],df.iloc[i]["Kwaliteitsactie"])
        flow.append(Paragraph(f"- {df.iloc[i]['Scenario']}: {route}",styles["JDENormal"]))
    flow.append(Spacer(1,10))

    # Disclaimer schuingedrukt
    flow.append(Paragraph("BPKV (Beste Prijs-Kwaliteit Verhouding) beoordeelt inschrijvingen op prijs en kwaliteit. "
                          "Prijspunten zijn steady en kwaliteitspunten volgen de gekozen schaal. "
                          "Adviezen zijn scenario-specifiek en objectief berekend.",styles["JDEItalic"]))

    def draw_bg(canvas,doc):
        canvas.setFillColor(colors.HexColor(PAGE_BEIGE))
        canvas.rect(0,0,doc.pagesize[0],doc.pagesize[1],fill=1,stroke=0)

    doc.build(flow,onFirstPage=draw_bg)
    pdf_buf.seek(0)
