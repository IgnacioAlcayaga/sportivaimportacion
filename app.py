import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Proyección Importación Sportiva", layout="wide")

# CARGA DE CREDENCIALES DESDE st.secrets
cred_json = st.secrets["google_credentials"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(cred_json, scopes=[
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(credentials)

# CONEXIÓN A LA HOJA
sheet = client.open("Proyeccion_Importacion_Sportiva").worksheet("proyeccion")
data = sheet.get_all_records()
df = pd.DataFrame(data)

# ASEGURAR TIPOS NUMÉRICOS
df["Utilidad ($)"] = pd.to_numeric(df["Utilidad ($)"], errors="coerce")
df["Margen (%)"] = pd.to_numeric(df["Margen (%)"], errors="coerce")

# TÍTULO
st.title("📦 Proyección de Importación - SPORTIVA")

# FILTROS INTERACTIVOS
col1, col2 = st.columns(2)
with col1:
    min_util = st.slider("Filtrar por utilidad mínima ($)", 0, int(df["Utilidad ($)"].max(skipna=True)), 0)
with col2:
    min_margen = st.slider("Filtrar por margen mínimo (%)", 0, 100, 30)

# FILTRAR DATAFRAME
df_filtrado = df[
    (df["Utilidad ($)"] >= min_util) &
    (df["Margen (%)"] >= min_margen)
]

# MOSTRAR RESULTADOS
st.markdown("### Resultados filtrados")
st.dataframe(df_filtrado, use_container_width=True)
