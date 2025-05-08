import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURACIÓN GENERAL
st.set_page_config(page_title="Proyección de Importación Sportiva", layout="wide")
st.title("Proyección de Importación Sportiva 2025")

# AUTENTICACIÓN CON GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(credentials)

# ABRIR ARCHIVO PRINCIPAL
SPREADSHEET_NAME = "Proyecciones"
spreadsheet = client.open(SPREADSHEET_NAME)

# LEER TODAS LAS HOJAS ventas_XXXX
ventas_dfs = []
for hoja in spreadsheet.worksheets():
    if hoja.title.startswith("ventas_"):
        df = pd.DataFrame(hoja.get_all_records())
        df["Año"] = hoja.title.split("_")[-1]
        ventas_dfs.append(df)

if not ventas_dfs:
    st.error("No se encontraron hojas con formato ventas_XXXX.")
    st.stop()

# UNIR Y NORMALIZAR DATOS
df_total = pd.concat(ventas_dfs, ignore_index=True)
df_total = df_total.rename(columns={
    "Producto / Servicio": "Producto",
    "Cantidad": "Cantidad",
    "Subtotal Bruto": "Precio Venta",
    "Costo neto unitario": "Costo Unitario"
})

# LIMPIEZA DE DATOS
df_total["Cantidad"] = pd.to_numeric(df_total["Cantidad"], errors="coerce")
df_total["Precio Venta"] = pd.to_numeric(df_total["Precio Venta"], errors="coerce")
df_total["Costo Unitario"] = pd.to_numeric(df_total["Costo Unitario"], errors="coerce")
df_total.dropna(subset=["Producto", "Cantidad", "Precio Venta", "Costo Unitario"], inplace=True)

# CÁLCULOS DE PROYECCIÓN
df_total["Costo Total"] = df_total["Cantidad"] * df_total["Costo Unitario"]

df_resumen = df_total.groupby("Producto").agg({
    "Cantidad": "sum",
    "Precio Venta": "sum",
    "Costo Total": "sum"
}).reset_index()

df_resumen["Utilidad Anual Estimada"] = df_resumen["Precio Venta"] - df_resumen["Costo Total"]
df_resumen["Margen Promedio (%)"] = (df_resumen["Utilidad Anual Estimada"] / df_resumen["Precio Venta"]) * 100
df_resumen["Proyección Anual Estimada"] = df_resumen["Cantidad"]

df_final = df_resumen[[
    "Producto", "Proyección Anual Estimada", "Cantidad", "Precio Venta",
    "Costo Total", "Utilidad Anual Estimada", "Margen Promedio (%)"
]].copy()

# SOBRESCRIBIR HOJA proyeccion_final
try:
    spreadsheet.del_worksheet(spreadsheet.worksheet("proyeccion_final"))
except gspread.exceptions.WorksheetNotFound:
    pass

n_filas = len(df_final) + 5
n_columnas = len(df_final.columns) + 2
spreadsheet.add_worksheet(title="proyeccion_final", rows=str(n_filas), cols=str(n_columnas))
spreadsheet.worksheet("proyeccion_final").update([df_final.columns.values.tolist()] + df_final.values.tolist())

# FILTROS INTERACTIVOS EN LA APP
df_final["Margen Promedio (%)"] = pd.to_numeric(df_final["Margen Promedio (%)"], errors="coerce")
df_final["Utilidad Anual Estimada"] = pd.to_numeric(df_final["Utilidad Anual Estimada"], errors="coerce")

col1, col2 = st.columns(2)
with col1:
    min_util = st.slider("Filtrar por utilidad mínima ($)", 0, int(df_final["Utilidad Anual Estimada"].max(skipna=True)), 500000)
with col2:
    min_margen = st.slider("Filtrar por margen mínimo (%)", 0, 100, 30)

# APLICAR FILTRO
filtro = (df_final["Utilidad Anual Estimada"] >= min_util) & (df_final["Margen Promedio (%)"] >= min_margen)
filtrados = df_final[filtro]

# MOSTRAR RESULTADOS
st.subheader(f"Productos sugeridos: {len(filtrados)}")
st.dataframe(filtrados, use_container_width=True)

# RESUMEN FINAL
total_utilidad = filtrados["Utilidad Anual Estimada"].sum()
total_productos = filtrados["Proyección Anual Estimada"].sum()

st.markdown(f'''
### Resumen General:
- Total proyectado a importar: **{int(total_productos):,} unidades**
- Utilidad estimada total: **${int(total_utilidad):,}**
''')
