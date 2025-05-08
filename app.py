import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Proyección de Importación Sportiva", layout="wide")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open("Proyeccion_Importacion_Sportiva").worksheet("proyeccion_final")
df = pd.DataFrame(sheet.get_all_records())

st.title("📦 Proyección Importación Sportiva 2025")

min_util = st.slider("Utilidad mínima", 0, int(df["Utilidad Anual Estimada"].max()), 500000)
min_margen = st.slider("Margen mínimo (%)", 0, 100, 30)

filtro = (df["Utilidad Anual Estimada"] >= min_util) & (df["Margen Promedio (%)"] >= min_margen)
filtrados = df[filtro]

st.dataframe(filtrados, use_container_width=True)
st.markdown(f"**{len(filtrados)} productos sugeridos para importar**")
