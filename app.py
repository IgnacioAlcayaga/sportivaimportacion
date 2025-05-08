import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from streamlit.runtime.secrets import secrets
import json

# CONFIGURACIÓN DE CONEXIÓN A GOOGLE SHEETS USANDO SECRETS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(secrets["GOOGLE_CREDS"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(credentials)

# CARGAR DATOS DESDE GOOGLE SHEETS
sheet = client.open("Proyeccion_Importacion_Sportiva").worksheet("proyeccion_final")
df = pd.DataFrame(sheet.get_all_records())

# INTERFAZ STREAMLIT
st.set_page_config(page_title="Proyección de Importación Sportiva", layout="wide")
st.title("📦 Proyección Importación Sportiva 2025")

min_util = st.slider("Utilidad mínima", 0, int(df["Utilidad Anual Estimada"].max()), 500000)
min_margen = st.slider("Margen mínimo (%)", 0, 100, 30)

filtro = (df["Utilidad Anual Estimada"] >= min_util) & (df["Margen Promedio (%)"] >= min_margen)
filtrados = df[filtro]

st.dataframe(filtrados, use_container_width=True)
st.markdown(f"**{len(filtrados)} productos sugeridos para importar**")
