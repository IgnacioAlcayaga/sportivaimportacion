import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Proyección Importación Sportiva", layout="wide")
st.title("📦 Proyección de Importación Sportiva 2025")

# CONEXIÓN A GOOGLE SHEETS USANDO st.secrets["gcp_service_account"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = st.secrets["gcp_service_account"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)

# ABRIR LA HOJA DE CÁLCULO Y CARGAR LA PESTAÑA DE PROYECCIONES
sheet = client.open("Proyecciones").worksheet("proyeccion_final")
df = pd.DataFrame(sheet.get_all_records())

# CONVERSIÓN A NÚMERO PARA FILTRAR
df["Utilidad Anual Estimada"] = pd.to_numeric(df["Utilidad Anual Estimada"], errors="coerce")
df["Margen Promedio (%)"] = pd.to_numeric(df["Margen Promedio (%)"], errors="coerce")

# VALIDACIÓN
if df.empty:
    st.warning("La hoja 'proyeccion_final' está vacía o no se pudo cargar.")
    st.stop()

# FILTROS
col1, col2 = st.columns(2)
with col1:
    min_util = st.slider("Filtrar por utilidad mínima ($)", 0, int(df["Utilidad Anual Estimada"].max(skipna=True)), 500000)
with col2:
    min_margen = st.slider("Filtrar por margen mínimo (%)", 0, 100, 30)

# APLICAR FILTROS
filtro = (df["Utilidad Anual Estimada"] >= min_util) & (df["Margen Promedio (%)"] >= min_margen)
filtrados = df[filtro]

# MOSTRAR RESULTADOS
st.subheader(f"📊 Productos sugeridos: {len(filtrados)}")
st.dataframe(filtrados, use_container_width=True)

# RESUMEN
total_utilidad = filtrados["Utilidad Anual Estimada"].sum()
total_productos = filtrados["Proyección Anual Estimada"].sum()

st.markdown(f"""
### 📈 Resumen General:
- 🧮 Total proyectado a importar: **{int(total_productos):,} unidades**
- 💰 Utilidad estimada total: **${int(total_utilidad):,}**
""")
