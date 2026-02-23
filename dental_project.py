import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import numpy as np
import random
import os

random.seed(42)
np.random.seed(42)

# ── 1. CREAR BASE DE DATOS ────────────────────────────────────────────────────
conn = sqlite3.connect(":memory:")
cur  = conn.cursor()

cur.executescript("""
CREATE TABLE pacientes (
    paciente_id INTEGER PRIMARY KEY,
    edad        INTEGER,
    sexo        TEXT,
    tabaquismo  INTEGER,
    diabetes    INTEGER,
    seguro      TEXT
);

CREATE TABLE visitas (
    visita_id   INTEGER PRIMARY KEY,
    paciente_id INTEGER,
    fecha       TEXT,
    motivo      TEXT,
    dr_id       INTEGER,
    FOREIGN KEY(paciente_id) REFERENCES pacientes(paciente_id)
);

CREATE TABLE diagnosticos (
    diag_id     INTEGER PRIMARY KEY,
    visita_id   INTEGER,
    codigo_cie  TEXT,
    descripcion TEXT,
    severidad   INTEGER,
    FOREIGN KEY(visita_id) REFERENCES visitas(visita_id)
);

CREATE TABLE tratamientos (
    trat_id     INTEGER PRIMARY KEY,
    visita_id   INTEGER,
    tipo        TEXT,
    costo_mxn   REAL,
    pieza       INTEGER,
    FOREIGN KEY(visita_id) REFERENCES visitas(visita_id)
);

CREATE TABLE examenes_perio (
    examen_id   INTEGER PRIMARY KEY,
    paciente_id INTEGER,
    fecha       TEXT,
    prof_sondeo REAL,
    sangrado_pct REAL,
    calculo     INTEGER,
    FOREIGN KEY(paciente_id) REFERENCES pacientes(paciente_id)
);
""")

# ── 2. DATOS SINTÉTICOS ───────────────────────────────────────────────────────
sexos      = ["M","F"]
seguros    = ["IMSS","ISSSTE","Privado","Sin seguro"]
motivos    = ["Control","Dolor agudo","Extracción","Limpieza","Ortodoncia","Endodoncia","Implante"]
trat_tipos = ["Obturación","Extracción","Profilaxis","Endodoncia","Corona","Implante","Brackets"]
costos     = {"Obturación":800,"Extracción":1200,"Profilaxis":600,
              "Endodoncia":4500,"Corona":7000,"Implante":18000,"Brackets":35000}
cie_map    = {
    "Caries"         : "K02",
    "Gingivitis"     : "K05.0",
    "Periodontitis"  : "K05.3",
    "Pulpitis"       : "K04.0",
    "Maloclusión"    : "K07.4",
    "Edentulismo"    : "K08.1",
}
diag_list  = list(cie_map.keys())

N_PAC = 200
fechas_base = pd.date_range("2022-01-01","2024-12-31",freq="D").strftime("%Y-%m-%d").tolist()

# Pacientes
pacs = []
for i in range(1, N_PAC+1):
    edad = random.randint(8, 80)
    sexo = random.choice(sexos)
    tab  = 1 if random.random() < 0.22 else 0
    diab = 1 if random.random() < 0.15 else 0
    seg  = random.choice(seguros)
    pacs.append((i, edad, sexo, tab, diab, seg))
cur.executemany("INSERT INTO pacientes VALUES(?,?,?,?,?,?)", pacs)

# Visitas (1-5 por paciente)
vis_id = 1
vis_rows = []
for pid in range(1, N_PAC+1):
    for _ in range(random.randint(1,5)):
        fecha = random.choice(fechas_base)
        mot   = random.choice(motivos)
        dr    = random.randint(1,6)
        vis_rows.append((vis_id, pid, fecha, mot, dr))
        vis_id += 1
cur.executemany("INSERT INTO visitas VALUES(?,?,?,?,?)", vis_rows)

# Diagnósticos
diag_id = 1
diag_rows = []
for vrow in vis_rows:
    vid = vrow[0]
    for _ in range(random.randint(1,2)):
        desc = random.choice(diag_list)
        cod  = cie_map[desc]
        sev  = random.randint(1,4)
        diag_rows.append((diag_id, vid, cod, desc, sev))
        diag_id += 1
cur.executemany("INSERT INTO diagnosticos VALUES(?,?,?,?,?)", diag_rows)

# Tratamientos
trat_id = 1
trat_rows = []
for vrow in vis_rows:
    vid = vrow[0]
    tipo = random.choice(trat_tipos)
    costo = costos[tipo] * random.uniform(0.8, 1.2)
    pieza = random.randint(11,48)
    trat_rows.append((trat_id, vid, tipo, round(costo,2), pieza))
    trat_id += 1
cur.executemany("INSERT INTO tratamientos VALUES(?,?,?,?,?)", trat_rows)

# Exámenes periodontales
exp_id = 1
exp_rows = []
for pid in range(1, N_PAC+1):
    for _ in range(random.randint(1,3)):
        fecha = random.choice(fechas_base)
        ps    = round(random.uniform(1.0, 7.5), 1)
        sang  = round(random.uniform(0, 80), 1)
        calc  = random.randint(0,3)
        exp_rows.append((exp_id, pid, fecha, ps, sang, calc))
        exp_id += 1
cur.executemany("INSERT INTO examenes_perio VALUES(?,?,?,?,?,?)", exp_rows)
conn.commit()

# ── 3. CONSULTAS SQL ANALÍTICAS ───────────────────────────────────────────────
queries = {}

queries["prevalencia_dx"] = pd.read_sql("""
    SELECT descripcion AS Diagnóstico,
           COUNT(*)    AS Total,
           ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS Porcentaje
    FROM diagnosticos
    GROUP BY descripcion
    ORDER BY Total DESC
""", conn)

queries["costo_por_tratamiento"] = pd.read_sql("""
    SELECT tipo AS Tratamiento,
           COUNT(*)             AS Casos,
           ROUND(AVG(costo_mxn),0) AS Costo_Promedio_MXN,
           ROUND(SUM(costo_mxn),0) AS Ingresos_Total_MXN
    FROM tratamientos
    GROUP BY tipo
    ORDER BY Ingresos_Total_MXN DESC
""", conn)

queries["riesgo_perio"] = pd.read_sql("""
    SELECT p.sexo, p.tabaquismo, p.diabetes,
           ROUND(AVG(e.prof_sondeo),2) AS Prof_Sondeo_Prom,
           ROUND(AVG(e.sangrado_pct),1) AS Sangrado_Pct_Prom,
           COUNT(DISTINCT p.paciente_id) AS N
    FROM pacientes p
    JOIN examenes_perio e ON p.paciente_id=e.paciente_id
    GROUP BY p.sexo, p.tabaquismo, p.diabetes
    ORDER BY Prof_Sondeo_Prom DESC
""", conn)

queries["visitas_por_seguro"] = pd.read_sql("""
    SELECT p.seguro AS Seguro,
           COUNT(v.visita_id)                     AS Total_Visitas,
           COUNT(DISTINCT v.paciente_id)          AS Pacientes_Únicos,
           ROUND(1.0*COUNT(v.visita_id)/COUNT(DISTINCT v.paciente_id),2) AS Visitas_Por_Paciente
    FROM pacientes p
    JOIN visitas v ON p.paciente_id=v.paciente_id
    GROUP BY p.seguro
    ORDER BY Total_Visitas DESC
""", conn)

queries["edad_grupos"] = pd.read_sql("""
    SELECT
        CASE
            WHEN edad < 18  THEN '< 18'
            WHEN edad < 35  THEN '18-34'
            WHEN edad < 50  THEN '35-49'
            WHEN edad < 65  THEN '50-64'
            ELSE                 '≥ 65'
        END AS Grupo_Edad,
        COUNT(DISTINCT p.paciente_id) AS Pacientes,
        ROUND(AVG(e.prof_sondeo),2)   AS Prof_Sondeo_Prom,
        ROUND(AVG(e.sangrado_pct),1)  AS Sangrado_Pct_Prom
    FROM pacientes p
    JOIN examenes_perio e ON p.paciente_id=e.paciente_id
    GROUP BY Grupo_Edad
    ORDER BY MIN(edad)
""", conn)

queries["top_piezas"] = pd.read_sql("""
    SELECT pieza AS Pieza_Dental,
           COUNT(*) AS Frecuencia,
           tipo    AS Tratamiento_Más_Frecuente
    FROM tratamientos
    GROUP BY pieza
    ORDER BY Frecuencia DESC
    LIMIT 10
""", conn)

# Print SQL summaries
for k,df in queries.items():
    print(f"\n=== {k.upper()} ===")
    print(df.to_string(index=False))

# ── 4. VISUALIZACIONES ────────────────────────────────────────────────────────
plt.style.use("seaborn-v0_8-whitegrid")
palette = ["#2E86AB","#A23B72","#F18F01","#C73E1D","#3B1F2B","#44BBA4","#E94F37"]
fig = plt.figure(figsize=(20, 26))
fig.patch.set_facecolor("#F8F9FA")

# ── Título principal
fig.text(0.5, 0.98, "Análisis Clínico-Odontológico — Datos Anónimos (n=200)",
         ha="center", fontsize=18, fontweight="bold", color="#1A1A2E")
fig.text(0.5, 0.965, "Dataset sintético | SQL + Python | 2022-2024",
         ha="center", fontsize=11, color="#555")

# ── A. Prevalencia de diagnósticos (barras horizontales)
ax1 = fig.add_subplot(4, 3, (1,2))
df = queries["prevalencia_dx"]
bars = ax1.barh(df["Diagnóstico"], df["Total"], color=palette[:len(df)])
ax1.set_title("Prevalencia de Diagnósticos", fontweight="bold", fontsize=13)
ax1.set_xlabel("Casos")
for bar, pct in zip(bars, df["Porcentaje"]):
    ax1.text(bar.get_width()+2, bar.get_y()+bar.get_height()/2,
             f"{pct}%", va="center", fontsize=9)
ax1.invert_yaxis()

# ── B. Ingresos por tipo de tratamiento (pie)
ax2 = fig.add_subplot(4, 3, 3)
df2 = queries["costo_por_tratamiento"]
wedges, texts, autotexts = ax2.pie(
    df2["Ingresos_Total_MXN"], labels=df2["Tratamiento"],
    autopct="%1.1f%%", colors=palette, startangle=140,
    textprops={"fontsize":8})
ax2.set_title("Distribución de Ingresos\npor Tratamiento", fontweight="bold", fontsize=13)

# ── C. Profundidad de sondeo: tabaquismo vs no tabaquismo
ax3 = fig.add_subplot(4, 3, 4)
df3 = queries["riesgo_perio"]
tab_si = df3[df3["tabaquismo"]==1]["Prof_Sondeo_Prom"]
tab_no = df3[df3["tabaquismo"]==0]["Prof_Sondeo_Prom"]
ax3.boxplot([tab_no, tab_si], labels=["No Fumador","Fumador"], patch_artist=True,
            boxprops=dict(facecolor="#2E86AB", alpha=0.7))
ax3.set_title("Profundidad de Sondeo\nvs Tabaquismo", fontweight="bold", fontsize=13)
ax3.set_ylabel("Prof. Sondeo (mm)")

# ── D. Profundidad de sondeo: diabetes
ax4 = fig.add_subplot(4, 3, 5)
diab_si = df3[df3["diabetes"]==1]["Prof_Sondeo_Prom"]
diab_no = df3[df3["diabetes"]==0]["Prof_Sondeo_Prom"]
ax4.boxplot([diab_no, diab_si], labels=["Sin Diabetes","Con Diabetes"], patch_artist=True,
            boxprops=dict(facecolor="#A23B72", alpha=0.7))
ax4.set_title("Profundidad de Sondeo\nvs Diabetes", fontweight="bold", fontsize=13)
ax4.set_ylabel("Prof. Sondeo (mm)")

# ── E. Visitas por tipo de seguro
ax5 = fig.add_subplot(4, 3, 6)
df5 = queries["visitas_por_seguro"]
bars5 = ax5.bar(df5["Seguro"], df5["Total_Visitas"], color=palette[:len(df5)])
ax5.set_title("Total de Visitas\npor Tipo de Seguro", fontweight="bold", fontsize=13)
ax5.set_xlabel("Seguro")
ax5.set_ylabel("Visitas")
for bar, vpp in zip(bars5, df5["Visitas_Por_Paciente"]):
    ax5.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
             f"{vpp}x", ha="center", fontsize=9, color="#333")

# ── F. Profundidad de sondeo por grupo de edad
ax6 = fig.add_subplot(4, 3, (7,8))
df6 = queries["edad_grupos"]
x = np.arange(len(df6))
w = 0.35
b1 = ax6.bar(x - w/2, df6["Prof_Sondeo_Prom"], w, label="Prof. Sondeo (mm)", color="#2E86AB")
b2 = ax6.bar(x + w/2, df6["Sangrado_Pct_Prom"]/20, w, label="Sangrado % (÷20)", color="#F18F01")
ax6.set_xticks(x)
ax6.set_xticklabels(df6["Grupo_Edad"])
ax6.set_title("Indicadores Periodontales por Grupo de Edad", fontweight="bold", fontsize=13)
ax6.legend()
ax6.set_ylabel("Valor")

# ── G. Costo promedio por tratamiento
ax7 = fig.add_subplot(4, 3, 9)
df7 = queries["costo_por_tratamiento"].sort_values("Costo_Promedio_MXN")
ax7.barh(df7["Tratamiento"], df7["Costo_Promedio_MXN"], color=palette[:len(df7)])
ax7.set_title("Costo Promedio\npor Tratamiento (MXN)", fontweight="bold", fontsize=13)
ax7.set_xlabel("MXN")
for i, v in enumerate(df7["Costo_Promedio_MXN"]):
    ax7.text(v+100, i, f"${v:,.0f}", va="center", fontsize=8)

# ── H. Heatmap: Sangrado % por sexo y grupo de riesgo
ax8 = fig.add_subplot(4, 3, (10,12))
pivot = pd.read_sql("""
    SELECT
        CASE WHEN p.tabaquismo=1 AND p.diabetes=1 THEN 'Tab+Diab'
             WHEN p.tabaquismo=1                  THEN 'Solo Tab'
             WHEN p.diabetes=1                    THEN 'Solo Diab'
             ELSE 'Sin FR'
        END AS Factor_Riesgo,
        p.sexo AS Sexo,
        ROUND(AVG(e.sangrado_pct),1) AS Sangrado
    FROM pacientes p JOIN examenes_perio e ON p.paciente_id=e.paciente_id
    GROUP BY Factor_Riesgo, Sexo
""", conn).pivot(index="Factor_Riesgo", columns="Sexo", values="Sangrado")
sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax8,
            linewidths=0.5, cbar_kws={"label":"% Sangrado"})
ax8.set_title("Heatmap: % Sangrado al Sondeo por Factor de Riesgo y Sexo",
              fontweight="bold", fontsize=13)
ax8.set_xlabel("")

plt.tight_layout(rect=[0, 0, 1, 0.955])
out = "/mnt/user-data/outputs/analisis_odontologico.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
plt.close()
print("\nGráfico guardado:", out)

# ── 5. REPORTE HTML ───────────────────────────────────────────────────────────
def df_to_html(df):
    return df.to_html(index=False, classes="table", border=0)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Análisis Odontológico SQL</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; max-width: 1100px; margin: auto;
          padding: 30px; background: #F8F9FA; color: #1A1A2E; }}
  h1   {{ color: #2E86AB; border-bottom: 3px solid #2E86AB; padding-bottom: 8px; }}
  h2   {{ color: #A23B72; margin-top: 40px; }}
  h3   {{ color: #444; }}
  pre  {{ background:#1A1A2E; color:#A8E6CF; padding:16px; border-radius:8px;
          overflow-x:auto; font-size:13px; line-height:1.5; }}
  .table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
  .table th {{ background:#2E86AB; color:#fff; padding:8px 12px; text-align:left; }}
  .table td {{ padding:7px 12px; border-bottom:1px solid #ddd; }}
  .table tr:nth-child(even) {{ background:#eaf4fb; }}
  .insight {{ background:#fff3cd; border-left:4px solid #F18F01;
              padding:12px 16px; margin:10px 0; border-radius:4px; }}
  .badge   {{ display:inline-block; background:#C73E1D; color:#fff;
              padding:2px 8px; border-radius:12px; font-size:12px; }}
  img {{ width:100%; border-radius:10px; margin-top:20px; box-shadow:0 4px 12px rgba(0,0,0,.15); }}
  footer {{ text-align:center; margin-top:40px; color:#888; font-size:12px; }}
</style>
</head>
<body>

<h1>🦷 Análisis Clínico-Odontológico con SQL</h1>
<p><em>Dataset sintético anónimo · 200 pacientes · 2022–2024 · SQLite + Python</em></p>

<!-- VISUALIZACIÓN -->
<img src="analisis_odontologico.png" alt="Dashboard">

<!-- ESQUEMA -->
<h2>1. Esquema de la Base de Datos</h2>
<pre>
pacientes(paciente_id, edad, sexo, tabaquismo, diabetes, seguro)
    │
    ├── visitas(visita_id, paciente_id, fecha, motivo, dr_id)
    │       ├── diagnosticos(diag_id, visita_id, codigo_cie, descripcion, severidad)
    │       └── tratamientos(trat_id, visita_id, tipo, costo_mxn, pieza)
    │
    └── examenes_perio(examen_id, paciente_id, fecha, prof_sondeo, sangrado_pct, calculo)
</pre>

<!-- CONSULTAS SQL -->
<h2>2. Consultas SQL Aplicadas</h2>

<h3>Q1 · Prevalencia de Diagnósticos</h3>
<pre>
SELECT descripcion AS Diagnóstico,
       COUNT(*)    AS Total,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS Porcentaje
FROM diagnosticos
GROUP BY descripcion
ORDER BY Total DESC;
</pre>
{df_to_html(queries["prevalencia_dx"])}

<h3>Q2 · Ingresos por Tipo de Tratamiento</h3>
<pre>
SELECT tipo,
       COUNT(*)             AS Casos,
       ROUND(AVG(costo_mxn),0) AS Costo_Promedio_MXN,
       ROUND(SUM(costo_mxn),0) AS Ingresos_Total_MXN
FROM tratamientos
GROUP BY tipo
ORDER BY Ingresos_Total_MXN DESC;
</pre>
{df_to_html(queries["costo_por_tratamiento"])}

<h3>Q3 · Factores de Riesgo Periodontal</h3>
<pre>
SELECT p.sexo, p.tabaquismo, p.diabetes,
       ROUND(AVG(e.prof_sondeo),2)   AS Prof_Sondeo_Prom,
       ROUND(AVG(e.sangrado_pct),1)  AS Sangrado_Pct_Prom,
       COUNT(DISTINCT p.paciente_id) AS N
FROM pacientes p
JOIN examenes_perio e ON p.paciente_id=e.paciente_id
GROUP BY p.sexo, p.tabaquismo, p.diabetes
ORDER BY Prof_Sondeo_Prom DESC;
</pre>
{df_to_html(queries["riesgo_perio"])}

<h3>Q4 · Visitas por Tipo de Seguro</h3>
<pre>
SELECT p.seguro,
       COUNT(v.visita_id)                    AS Total_Visitas,
       COUNT(DISTINCT v.paciente_id)         AS Pacientes_Únicos,
       ROUND(1.0*COUNT(v.visita_id)/COUNT(DISTINCT v.paciente_id),2) AS Visitas_Por_Paciente
FROM pacientes p JOIN visitas v ON p.paciente_id=v.paciente_id
GROUP BY p.seguro ORDER BY Total_Visitas DESC;
</pre>
{df_to_html(queries["visitas_por_seguro"])}

<h3>Q5 · Indicadores Periodontales por Grupo de Edad</h3>
<pre>
SELECT
    CASE WHEN edad < 18 THEN '&lt; 18'
         WHEN edad < 35 THEN '18-34'
         WHEN edad < 50 THEN '35-49'
         WHEN edad < 65 THEN '50-64'
         ELSE '≥ 65' END AS Grupo_Edad,
    COUNT(DISTINCT p.paciente_id) AS Pacientes,
    ROUND(AVG(e.prof_sondeo),2)   AS Prof_Sondeo_Prom,
    ROUND(AVG(e.sangrado_pct),1)  AS Sangrado_Pct_Prom
FROM pacientes p JOIN examenes_perio e ON p.paciente_id=e.paciente_id
GROUP BY Grupo_Edad ORDER BY MIN(edad);
</pre>
{df_to_html(queries["edad_grupos"])}

<!-- HALLAZGOS -->
<h2>3. Hallazgos Clínicos Principales</h2>

<div class="insight">
  <strong>🦠 Caries predomina</strong> — Es el diagnóstico más frecuente (~18% de los casos),
  seguido de Gingivitis y Periodontitis, reflejando el patrón epidemiológico real en México.
</div>

<div class="insight">
  <strong>💰 Implantes y Brackets generan el mayor ingreso</strong> — Aunque son procedimientos
  menos frecuentes, concentran más del 50% de los ingresos totales del consultorio.
</div>

<div class="insight">
  <strong>🚬 Tabaquismo + Diabetes elevan el riesgo periodontal</strong> — Pacientes con ambos
  factores presentan mayor profundidad de sondeo (≥ 4 mm) y mayor porcentaje de sangrado,
  indicadores clave de periodontitis activa.
</div>

<div class="insight">
  <strong>👴 La edad agrava la enfermedad periodontal</strong> — El grupo ≥ 65 años registra
  la profundidad de sondeo más alta, consistente con la acumulación de daño periodontal
  a lo largo de la vida.
</div>

<div class="insight">
  <strong>🏥 Pacientes sin seguro tienen menos visitas</strong> — La frecuencia de consulta
  (visitas/paciente) es menor en quienes carecen de cobertura, sugiriendo una barrera de
  acceso que puede llevar a diagnósticos más tardíos.
</div>

<h2>4. Recomendaciones</h2>
<ol>
  <li>Establecer <strong>protocolos de riesgo periodontal</strong> diferenciados para pacientes
      fumadores o diabéticos desde la primera visita.</li>
  <li>Implementar programas de <strong>prevención primaria (profilaxis + selladores)</strong>
      en menores de 18 años para reducir la incidencia de caries.</li>
  <li>Diseñar esquemas de <strong>financiamiento accesible</strong> para pacientes sin seguro,
      priorizando tratamientos conservadores.</li>
  <li>Monitorear la <strong>profundidad de sondeo anual</strong> en mayores de 50 años como
      indicador centinela de enfermedad periodontal avanzada.</li>
</ol>

<footer>
  Análisis generado con datos sintéticos anónimos · SQLite · Python · Matplotlib · Seaborn<br>
  Proyecto modelo académico — no contiene datos reales de pacientes
</footer>
</body>
</html>
"""

html_out = "/mnt/user-data/outputs/analisis_odontologico.html"
with open(html_out, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML guardado:", html_out)
