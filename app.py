import streamlit as st
import pandas as pd
import numpy as np
import gspread
import altair as alt
import io
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="📊 Sistema de Compras - Sportiva", layout="wide")
st.title("🧠 Sistema Inteligente de Decisión de Compras - Sportiva")

if "gcp_service_account" not in st.secrets:
    st.error("❌ Faltan credenciales para conectarse a Google Sheets.")
    st.stop()

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key("18XxehVk4sP8uPIfDoDyX1q_wFpkTA2e-Mf-wG2RcK5w")
worksheets = [ws for ws in sheet.worksheets() if ws.title.startswith("ventas_")]

dfs = []
for ws in worksheets:
    df = pd.DataFrame(ws.get_all_records())
    try:
        df['Año'] = int(ws.title.split('_')[1])
    except:
        df['Año'] = None
    dfs.append(df)
ventas_df = pd.concat(dfs, ignore_index=True)

st.success("✅ Conexión y carga de datos exitosa.")

ventas_df['Fecha'] = pd.to_datetime(ventas_df['Fecha de Emisión'], errors='coerce')
ventas_df['Precio Neto Unitario'] = pd.to_numeric(ventas_df['Precio Neto Unitario'], errors='coerce').fillna(0)
ventas_df['Cantidad'] = pd.to_numeric(ventas_df['Cantidad'], errors='coerce').fillna(0)
ventas_df['Venta'] = ventas_df['Precio Neto Unitario'] * ventas_df['Cantidad']
ventas_df['Mes'] = ventas_df['Fecha'].dt.to_period('M')

ultimo_año = ventas_df['Año'].max()
ventas_anuales = ventas_df[ventas_df['Año'] == ultimo_año].groupby(['SKU', 'Producto / Servicio']).agg(
    Venta_Anual=('Venta', 'sum')
).reset_index()

ventas_anuales['Demanda_Proyectada'] = ventas_anuales['Venta_Anual']

Z = 1.65
stds = ventas_df.groupby('SKU')['Venta'].std().fillna(0)
ventas_anuales['Stock_Seguridad'] = ventas_anuales['SKU'].map(lambda x: round(Z * stds.get(x, 0)))

costos = dict(zip(ventas_anuales['SKU'], np.random.randint(3000, 7000, len(ventas_anuales))))
ventas_anuales['Costo_Unitario'] = ventas_anuales['SKU'].map(costos)
ventas_anuales['Unidades'] = ventas_anuales['Venta_Anual'] / ventas_anuales['Costo_Unitario']
ventas_anuales['Costo_Total'] = ventas_anuales['Unidades'] * ventas_anuales['Costo_Unitario']
ventas_anuales['Utilidad_Anual'] = ventas_anuales['Venta_Anual'] - ventas_anuales['Costo_Total']
ventas_anuales['Margen_%'] = round(ventas_anuales['Utilidad_Anual'] / ventas_anuales['Venta_Anual'] * 100, 1)
ventas_anuales['Recomendacion_Compra'] = ventas_anuales['Demanda_Proyectada'] + ventas_anuales['Stock_Seguridad']

st.sidebar.header("🔍 Filtros")
margen_min = st.sidebar.slider("Margen mínimo (%)", 0, 100, 0)
util_min = st.sidebar.number_input("Utilidad mínima", 0, step=1000)
venta_min = st.sidebar.number_input("Venta mínima", 0, step=1000)

filtros = ventas_anuales[
    (ventas_anuales['Margen_%'] >= margen_min) &
    (ventas_anuales['Utilidad_Anual'] >= util_min) &
    (ventas_anuales['Venta_Anual'] >= venta_min)
]

with st.expander("📅 Análisis estacional por año"):
    st.markdown("Compara las ventas mensuales por SKU o categoría entre años.")
    agrupador = st.selectbox("Agrupar estacionalidad por:", ["SKU", "Producto / Servicio"], key="estacional")
    anios = sorted(ventas_df['Año'].dropna().unique())
    categorias = ventas_df[agrupador].dropna().unique()
    seleccion = st.multiselect(f"Selecciona {agrupador}(s):", opciones := list(categorias), default=opciones[:1])

    df_filtrado = ventas_df[ventas_df[agrupador].isin(seleccion)].copy()
    df_filtrado['Mes_Num'] = df_filtrado['Fecha'].dt.month
    df_filtrado['Mes_Texto'] = df_filtrado['Fecha'].dt.strftime('%b')

    resumen_estacional = df_filtrado.groupby(['Año', 'Mes_Num', 'Mes_Texto'])['Venta'].sum().reset_index()
    resumen_estacional = resumen_estacional.sort_values(['Año', 'Mes_Num'])

    pivot_ano = resumen_estacional.pivot(index='Mes_Num', columns='Año', values='Venta').fillna(0)
    pivot_ano['Mes'] = resumen_estacional.groupby('Mes_Num')['Mes_Texto'].first()
    pivot_ano = pivot_ano.set_index('Mes')

    st.dataframe(pivot_ano.style.format("{:,.0f}"))
    st.line_chart(pivot_ano)

with st.expander("🚨 Alertas de stock y recomendaciones"):
    stock_actual = pd.Series(np.random.randint(0, 100, len(filtros)), index=filtros['SKU'])
    lead_times = {}  # completar si se desea automatizar con proveedores

    alertas = []
    for _, row in filtros.iterrows():
        sku = row['SKU']
        demanda_mensual = row['Demanda_Proyectada'] / 12
        if isinstance(demanda_mensual, pd.Series):
            demanda_mensual = float(demanda_mensual.iloc[0]) if not demanda_mensual.empty else 0
        elif isinstance(demanda_mensual, pd.DataFrame):
            demanda_mensual = float(demanda_mensual.values[0][0])
        cobertura = stock_actual.get(sku, 0)
        lead_time_meses = lead_times.get(sku, 30) / 30
        cobertura_meses = cobertura / demanda_mensual if demanda_mensual > 0 else 0

        if cobertura_meses < lead_time_meses:
            alertas.append((sku, row['Producto / Servicio'], cobertura_meses, lead_time_meses))

    if alertas:
        st.error("🚨 Productos con cobertura menor al lead time estimado:")
        df_alertas = pd.DataFrame(alertas, columns=['SKU', 'Producto / Servicio', 'Cobertura (meses)', 'Lead Time (meses)'])
        st.dataframe(df_alertas)
    else:
        st.success("✅ Todos los productos tienen cobertura suficiente.")
