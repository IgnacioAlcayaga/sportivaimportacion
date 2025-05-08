import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Proyección Importación Sportiva", layout="wide")
st.title("📦 Proyección de Importación Sportiva 2025")

# AUTENTICACIÓN USANDO SECRETO: gcp_service_account
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(credentials)

# CARGA DE DATOS DESDE GOOGLE SHEETS
sheet = client.open("Proyecciones").worksheet("proyeccion_final")
df = pd.DataFrame(sheet.get_all_records())

# CONVERSIÓN A NÚMEROS
df["Utilidad Anual Estimada"] = pd.to_numeric(df["Utilidad Anual Estimada"], errors="coerce")
df["Margen Promedio (%)"] = pd.to_numeric(df["Margen Promedio (%)"], errors="coerce")
df["Proyección Anual Estimada"] = pd.to_numeric(df["Proyección Anual Estimada"], errors="coerce")

# VALIDACIÓN DE CONTENIDO
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

# MOSTRAR DATOS FILTRADOS
st.subheader(f"📊 Productos sugeridos: {len(filtrados)}")
st.dataframe(filtrados, use_container_width=True)

# RESUMEN FINAL
total_utilidad = filtrados["Utilidad Anual Estimada"].sum()
total_productos = filtrados["Proyección Anual Estimada"].sum()
st.markdown(f"""
### 📈 Resumen General:
- 🧮 Total proyectado a importar: **{int(total_productos):,} unidades**
- 💰 Utilidad estimada total: **${int(total_utilidad):,}**
""")
