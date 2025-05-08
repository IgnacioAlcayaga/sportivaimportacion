import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from streamlit.runtime.secrets import secrets

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Proyección Importación Sportiva", layout="wide")

st.title("📦 Proyección de Importación Sportiva 2025")
st.markdown("Visualiza y filtra los productos recomendados para importar basados en ventas históricas.")

# CONFIGURACIÓN DE CONEXIÓN A GOOGLE SHEETS (usando secret GOOGLE_CREDS)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(secrets["GOOGLE_CREDS"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(credentials)

# ABRIR ARCHIVO Y PESTAÑA
sheet = client.open("Proyecciones").worksheet("proyeccion_final")
df = pd.DataFrame(sheet.get_all_records())

# VALIDACIÓN BÁSICA
if df.empty:
    st.warning("La hoja 'proyeccion_final' está vacía o no fue cargada correctamente.")
    st.stop()

# FILTROS INTERACTIVOS
col1, col2 = st.columns(2)
with col1:
    min_util = st.slider("Filtrar por utilidad mínima ($)", 0, int(df["Utilidad Anual Estimada"].max()), 500000)
with col2:
    min_margen = st.slider("Filtrar por margen mínimo (%)", 0, 100, 30)

# APLICAR FILTRO
filtro = (df["Utilidad Anual Estimada"] >= min_util) & (df["Margen Promedio (%)"] >= min_margen)
filtrados = df[filtro]

# MOSTRAR RESULTADOS
st.subheader(f"📊 Productos que cumplen con los filtros: {len(filtrados)}")
st.dataframe(filtrados, use_container_width=True)

# RESUMEN FINAL
total_utilidad = filtrados["Utilidad Anual Estimada"].sum()
total_productos = filtrados["Proyección Anual Estimada"].sum()
st.markdown(f"""
**Resumen:**

- Total proyectado a importar: `{int(total_productos)} unidades`
- Utilidad estimada total: `${int(total_utilidad):,}`
""")
