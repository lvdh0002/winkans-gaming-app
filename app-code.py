 import streamlit as st
 import pandas as pd
 import numpy as np
 
 # --- Page Config ---
 st.set_page_config(page_title="Winkans Berekening Tool", layout="wide")
 st.title("Tool om winkansen te berekenen o.b.v. de BPKV-methode (Beste Prijs Kwaliteit Verhouding)")
 
 # --- Stap 1: Beoordelingsmethodiek ---
 st.sidebar.header("Stap 1: Beoordelingsmethodiek")
+
+def _sync_from_quality() -> None:
+    st.session_state.price_input = 100 - st.session_state.quality_input
+
+def _sync_from_price() -> None:
+    st.session_state.quality_input = 100 - st.session_state.price_input
+
 col1, col2 = st.sidebar.columns(2)
 with col1:
-    kwaliteit_pct = st.number_input(
-        "Kwaliteit (%)", min_value=0, max_value=100,
-        value=60, step=1,
+    st.number_input(
+        "Kwaliteit (%)",
+        min_value=0,
+        max_value=100,
+        value=60,
+        step=1,
         help="Vul kwaliteit in; prijs wordt automatisch 100 - kwaliteit",
-        key="quality_input"
+        key="quality_input",
+        on_change=_sync_from_quality,
     )
 with col2:
-    prijs_pct = st.number_input(
-        "Prijs (%)", min_value=0, max_value=100,
-        value=40, step=1,
+    st.number_input(
+        "Prijs (%)",
+        min_value=0,
+        max_value=100,
+        value=40,
+        step=1,
         help="Vul prijs in; kwaliteit wordt automatisch 100 - prijs",
-        key="price_input"
+        key="price_input",
+        on_change=_sync_from_price,
     )
-# Synchroniseer
-if st.session_state.quality_input + st.session_state.price_input != 100:
-    # als kwaliteit net is aangepast
-    if st.session_state.quality_input != kwaliteit_pct:
-        prijs_pct = 100 - kwaliteit_pct
-        st.session_state.price_input = prijs_pct
-    else:
-        kwaliteit_pct = 100 - prijs_pct
-        st.session_state.quality_input = kwaliteit_pct
-# Toon
+
+kwaliteit_pct = st.session_state.quality_input
+prijs_pct = st.session_state.price_input
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
 
diff --git a/app-code.py b/app-code.py
index db861f6a2829995933135f9035cb8e68d2847884..ac0d13585c57880fc69e73e87fbff7a3e57ba96b 100644
--- a/app-code.py
+++ b/app-code.py
@@ -88,119 +96,104 @@ max_price_points = st.sidebar.number_input("Max punten Prijs", min_value=1, valu
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
-    # Functie om schaalscore naar punten te converteren
     def score_to_points(s, maxp):
-        return (s/100)*maxp if max_scale>10 else (s/max_scale)*maxp
+        return (s/100)*maxp if max_scale > 10 else (s/max_scale)*maxp
 
-    # Bereken JDE's punten
     jde_quality_pts = sum(
         score_to_points(verwachte_scores_eigen[c], max_points_criteria[c])
         for c in criteria
     )
     jde_price_pts = eigen_prijs_points
     jde_total = jde_quality_pts + jde_price_pts
 
-    # Vergelijk JDE met elke concurrent
-    vergelijking = []
+    overzicht = []
     for s in scenarios:
         comp_quality_pts = sum(
             score_to_points(s['kval_scores'][c], max_points_criteria[c])
             for c in criteria
         )
         comp_price_pts = s['prijs_pts']
         comp_total = comp_quality_pts + comp_price_pts
-        # Bepaal status
+
         if jde_total > comp_total:
-            status = 'WIN'
+            status = "WIN"
         elif jde_total < comp_total:
-            status = 'LOSE'
+            status = "LOSE"
         else:
-            status = 'DRAW'
-        vergelijking.append({
-            'Scenario': s['naam'],
-            'JDE (K+P)': f"{round(jde_quality_pts,1)}+{round(jde_price_pts,1)}={round(jde_total,1)}",
-            'Comp (K+P)': f"{round(comp_quality_pts,1)}+{round(comp_price_pts,1)}={round(comp_total,1)}",
-            'Status': status
-        })
-    df_verg = pd.DataFrame(vergelijking).set_index('Scenario')
-    st.subheader("Vergelijking JDE vs scenario")
-    st.table(df_verg)
-
-        # Prijsadvies om te winnen
-    st.subheader("Prijsadvies om te winnen")
-    prijs_advies = []
-    for row in vergelijking:
-        if row['Status'] == 'LOSE':
-            comp_tot = float(row['Comp (K+P)'].split('=')[-1])
-            need_pts = comp_tot - jde_quality_pts + 0.01
-            # bereken maximale allowed overpricing
-            max_over_pct = (1 - need_pts/max_price_points) * 100
-            # huidige overpricing = margin_pct
-            # bereken hoeveel procent zakken
+            status = "DRAW"
+
+        st.markdown(f"#### {s['naam']}")
+        st.markdown(f"- Resultaat: {status}")
+        st.markdown(f"- JDE: {jde_total:.1f} punten")
+        st.markdown(f"- {s['naam']}: {comp_total:.1f} punten")
+
+        max_over_pct = None
+        qual_hint = ""
+        if status == "LOSE":
+            need_pts = comp_total - jde_quality_pts + 0.01
+            max_over_pct = (1 - need_pts / max_price_points) * 100
             drop_pct = margin_pct - max_over_pct
-            prijs_advies.append({
-                'Scenario': row['Scenario'],
-                'Max % duurder dan goedkoopste': f"{max_over_pct:.1f}%",
-                'Moet zakken met (%)': f"{drop_pct:.1f}%"
-            })
-    if prijs_advies:
-        df_adv_prijs = pd.DataFrame(prijs_advies).set_index('Scenario')
-        st.table(df_adv_prijs)
-    else:
-        st.write("JDE wint qua prijs in alle scenario's.")
-
-    # Kwaliteitsadvies om te winnen bij gelijkblijvende prijs
-    st.subheader("Kwaliteitsadvies om te winnen bij gelijkblijvende prijs")
-("JDE wint qua prijs in alle scenario's.")
-
-    # Kwaliteitsadvies om te winnen
-st.subheader("Kwaliteitsadvies om te winnen bij gelijkblijvende prijs")
-kwal_advies = []
-for row in vergelijking:
-    if row['Status'] == 'LOSE':
-        comp_tot = float(row['Comp (K+P)'].split('=')[-1])
-        gap = comp_tot - jde_total + 0.01
-        for c in criteria:
-            current = verwachte_scores_eigen[c]
-            for nxt in scale_values:
-                if nxt > current:
-                    gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(current, max_points_criteria[c])
-                    if gain >= gap:
-                        kwal_advies.append({
-                            'Scenario': row['Scenario'],
-                            'Criterium': c,
-                            'Huidig→Nodig': f"{current}→{nxt}",
-                            'Extra punten': round(gain,1)
-                        })
-                        break
-    if kwal_advies:
-        df_adv_kw = pd.DataFrame(kwal_advies).set_index('Scenario')
-        st.table(df_adv_kw)
-    else:
-        st.write("Geen enkele kwaliteitsverhoging in één stap is voldoende om te winnen.")
+            st.markdown(
+                f"- Max % duurder dan goedkoopste om gelijk te spelen: {max_over_pct:.1f}% "
+                f"(nu {margin_pct:.1f}%, zak {drop_pct:.1f}%)"
+            )
+
+            gap = comp_total - jde_total + 0.01
+            suggestion = None
+            for c in criteria:
+                current = verwachte_scores_eigen[c]
+                for nxt in scale_values:
+                    if nxt > current:
+                        gain = score_to_points(nxt, max_points_criteria[c]) - score_to_points(
+                            current, max_points_criteria[c]
+                        )
+                        if gain >= gap:
+                            suggestion = (c, current, nxt, gain)
+                            break
+                if suggestion:
+                    break
+            if suggestion:
+                c, cur, nxt, gain = suggestion
+                qual_hint = f"{c}: {cur}→{nxt}"
+                st.markdown(f"- Verhoog {c} van {cur} naar {nxt} ({gain:.1f} ptn) om te winnen")
+            else:
+                st.markdown("- Met één scoreverhoging kun je niet winnen.")
+
+        overzicht.append(
+            {
+                "Scenario": s["naam"],
+                "JDE": round(jde_total, 1),
+                "Concurrent": round(comp_total, 1),
+                "Status": status,
+                "Max % duurder": f"{max_over_pct:.1f}%" if max_over_pct is not None else "",
+                "Kwaliteitsadvies": qual_hint,
+            }
+        )
+
+    df_overzicht = pd.DataFrame(overzicht).set_index("Scenario")
+    st.subheader("Overzicht alle scenario's")
+    st.table(df_overzicht)
 else:
     st.info("Klik op 'Bereken winkansen' om te starten.")
-
-
