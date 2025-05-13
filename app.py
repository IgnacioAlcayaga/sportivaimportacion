import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURACIÓN
st.set_page_config(layout="wide", page_title="Decisión de Compras Sportiva", page_icon="📊")
st.title("🧠 Sistema Inteligente de Decisión de Compras - Sportiva")

# CONEXIÓN A GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(credentials)

spreadsheet = client.open("Proyecciones")
ventas_dfs = []

for hoja in spreadsheet.worksheets():
    if hoja.title.startswith("ventas_"):
        df = pd.DataFrame(hoja.get_all_records())
        df["Año"] = hoja.title.split("_")[-1]
        ventas_dfs.append(df)

if not ventas_dfs:
    st.error("No se encontraron hojas con formato ventas_XXXX.")
    st.stop()

# UNIR Y LIMPIAR DATOS
df = pd.concat(ventas_dfs, ignore_index=True)
df = df.rename(columns={
    "Producto / Servicio": "Producto",
    "Cantidad": "Cantidad",
    "Subtotal Bruto": "Precio Venta",
    "Costo neto unitario": "Costo Unitario"
})

df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce")
df["Precio Venta"] = pd.to_numeric(df["Precio Venta"], errors="coerce")
df["Costo Unitario"] = pd.to_numeric(df["Costo Unitario"], errors="coerce")
df.dropna(subset=["Producto", "Cantidad", "Precio Venta", "Costo Unitario"], inplace=True)

# ANÁLISIS POR PRODUCTO
agrupado = df.groupby("Producto").agg(
    cantidad_total=("Cantidad", "sum"),
    precio_total=("Precio Venta", "sum"),
    costo_total=("Costo Unitario", lambda x: (x.mean() * df.loc[x.index, "Cantidad"]).sum()),
    frecuencia=("Año", "count"),
    promedio_mensual=("Cantidad", lambda x: x.sum() / len(set(df.loc[x.index, "Año"])) / 12),
    desviacion=("Cantidad", lambda x: np.std(x))
).reset_index()

agrupado["utilidad_total"] = agrupado["precio_total"] - agrupado["costo_total"]
agrupado["margen"] = (agrupado["utilidad_total"] / agrupado["precio_total"]) * 100
agrupado["stock_seguridad"] = agrupado["desviacion"] * 1.5  # buffer por variabilidad
agrupado["sugerencia_compra"] = (agrupado["promedio_mensual"] * 12 + agrupado["stock_seguridad"]).round()

# MOSTRAR TABLA CON FILTROS
st.markdown("### 🧾 Análisis Consolidado y Sugerencias de Compra")
filtro_utilidad = st.slider("Filtrar por utilidad mínima ($):", 0, int(agrupado["utilidad_total"].max()), 100000)
filtro_margen = st.slider("Filtrar por margen mínimo (%):", 0, 100, 20)

filtrado = agrupado[
    (agrupado["utilidad_total"] >= filtro_utilidad) &
    (agrupado["margen"] >= filtro_margen)
]

st.dataframe(filtrado[[
    "Producto", "cantidad_total", "promedio_mensual", "stock_seguridad",
    "sugerencia_compra", "utilidad_total", "margen"
]].sort_values("sugerencia_compra", ascending=False), use_container_width=True)

# RESUMEN FINAL
total_sugerido = int(filtrado["sugerencia_compra"].sum())
total_utilidad = int(filtrado["utilidad_total"].sum())

st.markdown(f"**Total unidades sugeridas a importar:** {total_sugerido:,}")
st.markdown(f"**Utilidad estimada total:** ${total_utilidad:,}")
