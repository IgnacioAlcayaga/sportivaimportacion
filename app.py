import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Proyección de Importación - Sportiva", layout="wide")

# Autenticación con Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
gc = gspread.authorize(credentials)

# Conexión a la Google Sheet
SPREADSHEET_NAME = "Proyecciones"
sh = gc.open(SPREADSHEET_NAME)

# Leer todas las hojas que comienzan con ventas_
ventas_dfs = []
for hoja in sh.worksheets():
    if hoja.title.startswith("ventas_"):
        df = pd.DataFrame(hoja.get_all_records())
        df["anio"] = hoja.title.split("_")[-1]
        ventas_dfs.append(df)

if not ventas_dfs:
    st.error("No se encontraron hojas de ventas.")
    st.stop()

df_total = pd.concat(ventas_dfs, ignore_index=True)

# Validaciones básicas
if "Producto/Servicio" not in df_total.columns or "Cantidad" not in df_total.columns:
    st.error("Las hojas deben tener columnas 'Producto/Servicio' y 'Cantidad'")
    st.stop()

# Agrupamos por producto
df_agrupado = (
    df_total.groupby("Producto/Servicio")["Cantidad"]
    .agg(["sum", "count", "mean"])
    .rename(columns={"sum": "total_vendido", "count": "frecuencia", "mean": "prom_mensual"})
    .reset_index()
)

# Proyección anual
df_agrupado["proyeccion_2025"] = (df_agrupado["prom_mensual"] * 12).round().astype(int)

# Sobrescribimos la hoja proyeccion_final
try:
    sh.del_worksheet(sh.worksheet("proyeccion_final"))
except gspread.exceptions.WorksheetNotFound:
    pass

ws = sh.add_worksheet(title="proyeccion_final", rows="1000", cols="10")
headers = df_agrupado.columns.tolist()
ws.append_row(headers)
ws.append_rows(df_agrupado.values.tolist())

st.success("✅ Hoja 'proyeccion_final' creada/actualizada exitosamente.")

# Mostrar en la app
st.title("📦 Proyección de Importación Anual")
st.dataframe(df_agrupado, use_container_width=True)

# Filtros
with st.expander("🔍 Filtrar por producto"):
    producto = st.selectbox("Selecciona un producto", options=[""] + df_agrupado["Producto/Servicio"].unique().tolist())
    if producto:
        st.dataframe(df_agrupado[df_agrupado["Producto/Servicio"] == producto])
