import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURACIÓN GENERAL
st.set_page_config(page_title="Proyección Importación Sportiva", layout="wide")
st.title("📦 Proyección de Importación Sportiva 2025")

# CONECTAR CON GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(credentials)

# ABRIR ARCHIVO PRINCIPAL
spreadsheet = client.open("Proyecciones")
sheet_names = [ws.title for ws in spreadsheet.worksheets() if ws.title.startswith("ventas_")]

# LEER Y COMBINAR TODAS LAS HOJAS ventas_20XX
df_list = []
for name in sheet_names:
    data = spreadsheet.worksheet(name).get_all_records()
    df = pd.DataFrame(data)
    df["Año"] = name.split("_")[1]
    df_list.append(df)

# UNIR TODO
ventas = pd.concat(df_list, ignore_index=True)

# ASEGURAR TIPOS NUMÉRICOS
ventas["Cantidad"] = pd.to_numeric(ventas["Cantidad"], errors="coerce")
ventas["Subtotal Bruto"] = pd.to_numeric(ventas["Subtotal Bruto"], errors="coerce")
ventas["Costo neto unitario"] = pd.to_numeric(ventas["Costo neto unitario"], errors="coerce")

# AGRUPAR POR PRODUCTO
ventas["Costo Total"] = ventas["Cantidad"] * ventas["Costo neto unitario"]
agrupado = ventas.groupby("Producto / Servicio").agg({
    "Cantidad": "sum",
    "Subtotal Bruto": "sum",
    "Costo Total": "sum"
}).reset_index()

agrupado["Utilidad Anual Estimada"] = agrupado["Subtotal Bruto"] - agrupado["Costo Total"]
agrupado["Margen Promedio (%)"] = (agrupado["Utilidad Anual Estimada"] / agrupado["Subtotal Bruto"]) * 100
agrupado["Proyección Anual Estimada"] = agrupado["Cantidad"]

# REORDENAR COLUMNAS
df_final = agrupado[[
    "Producto / Servicio", "Proyección Anual Estimada", "Cantidad", "Subtotal Bruto",
    "Costo Total", "Utilidad Anual Estimada", "Margen Promedio (%)"
]]

# SOBRESCRIBIR HOJA proyeccion_final
try:
    spreadsheet.del_worksheet(spreadsheet.worksheet("proyeccion_final"))
except:
    pass  # Si no existe, no pasa nada

spreadsheet.add_worksheet(title="proyeccion_final", rows=str(len(df_final)+5), cols=str(len(df_final.columns)))
spreadsheet.worksheet("proyeccion_final").update([df_final.columns.values.tolist()] + df_final.values.tolist())

# FILTROS INTERACTIVOS
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
st.subheader(f"📊 Productos sugeridos: {len(filtrados)}")
st.dataframe(filtrados, use_container_width=True)

# RESUMEN
st.markdown(f"""
### 📈 Resumen General:
- 🧮 Total proyectado a importar: **{int(filtrados['Proyección Anual Estimada'].sum()):,} unidades**
- 💰 Utilidad estimada total: **${int(filtrados['Utilidad Anual Estimada'].sum()):,}**
""")
