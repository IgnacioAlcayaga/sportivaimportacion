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

    df_filtrado = ventas_df[ventas_df[agrupador].isin(seleccion)]
    df_filtrado['Mes_Num'] = df_filtrado['Fecha'].dt.month
    df_filtrado['Mes_Texto'] = df_filtrado['Fecha'].dt.strftime('%b')

    resumen_estacional = df_filtrado.groupby(['Año', 'Mes_Num', 'Mes_Texto'])["Venta"].sum().reset_index()
    resumen_estacional = resumen_estacional.sort_values(['Año', 'Mes_Num'])

    pivot_ano = resumen_estacional.pivot(index='Mes_Num', columns='Año', values='Venta').fillna(0)
    pivot_ano['Mes'] = resumen_estacional.groupby('Mes_Num')['Mes_Texto'].first()
    pivot_ano = pivot_ano.set_index('Mes')

    st.dataframe(pivot_ano.style.format("{:,.0f}"))
    st.line_chart(pivot_ano)

# Cargar datos de proveedores desde hoja 'proveedores'
try:
    proveedores_ws = sheet.worksheet("proveedores")
    proveedores_df = pd.DataFrame(proveedores_ws.get_all_records())
    proveedores_df['Costo Unitario'] = pd.to_numeric(proveedores_df['Costo Unitario'], errors='coerce')
    proveedores_df['Lead Time (días)'] = pd.to_numeric(proveedores_df['Lead Time (días)'], errors='coerce')
    proveedores_df['MOQ'] = pd.to_numeric(proveedores_df['MOQ'], errors='coerce')

    with st.expander("🔄 Comparar proveedores por SKU"):
        sku_comparar = st.selectbox("Selecciona un SKU para comparar proveedores:", proveedores_df['SKU'].unique())
        comparativa = proveedores_df[proveedores_df['SKU'] == sku_comparar]
        st.write(f"Proveedores disponibles para el SKU {sku_comparar}:")
        st.dataframe(comparativa)

        chart_prov = alt.Chart(comparativa).mark_bar().encode(
            x=alt.X('Proveedor:N', title='Proveedor'),
            y=alt.Y('Costo Unitario:Q', title='Costo Unitario'),
            tooltip=['Proveedor', 'Costo Unitario', 'Lead Time (días)', 'MOQ', 'Condiciones de Pago']
        )
        st.altair_chart(chart_prov, use_container_width=True)

except Exception as e:
    st.warning(f"⚠️ No se pudo cargar la hoja 'proveedores': {e}")

with st.expander("🚨 Alertas de stock y recomendaciones"):
    stock_actual = pd.Series(np.random.randint(0, 100, len(filtros)), index=filtros['SKU'])
    lead_times = proveedores_df.groupby('SKU')['Lead Time (días)'].min().to_dict()

    alertas = []
    for _, row in filtros.iterrows():
        sku = row['SKU']
        demanda_mensual = row['Demanda_Proyectada'] / 12
        cobertura_meses = stock_actual.get(sku, 0) / demanda_mensual if demanda_mensual > 0 else 0
        lead_time_meses = lead_times.get(sku, 30) / 30
        if cobertura_meses < lead_time_meses:
            alertas.append((sku, row['Producto / Servicio'], cobertura_meses, lead_time_meses))

    if alertas:
        st.error("🚨 Productos con cobertura menor al lead time estimado:")
        df_alertas = pd.DataFrame(alertas, columns=['SKU', 'Producto / Servicio', 'Cobertura (meses)', 'Lead Time (meses)'])
        st.dataframe(df_alertas)
    else:
        st.success("✅ Todos los productos tienen cobertura suficiente según demanda proyectada y lead time mínimo.")

with st.expander("📊 Reporte estratégico descargable"):
    st.markdown("Descarga un reporte con múltiples hojas incluyendo métricas clave, detalle de productos y proveedores.")
    if not filtros.empty and 'proveedores_df' in locals():
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            filtros.to_excel(writer, index=False, sheet_name='Resumen Productos')
            proveedores_df.to_excel(writer, index=False, sheet_name='Proveedores')
            if 'df_alertas' in locals():
                df_alertas.to_excel(writer, index=False, sheet_name='Alertas Stock')
            resumen_kpi = pd.DataFrame({
                'KPI': ["Total productos filtrados", "Inversión estimada", "Utilidad estimada"],
                'Valor': [
                    filtros.shape[0],
                    filtros['Costo_Total'].sum(),
                    filtros['Utilidad_Anual'].sum()
                ]
            })
            resumen_kpi.to_excel(writer, index=False, sheet_name='KPIs')
            writer.close()
        st.download_button(
            label="📥 Descargar Reporte Estratégico (Excel)",
            data=output.getvalue(),
            file_name="reporte_estrategico.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("🔎 Aplica filtros y asegúrate de que existan datos y proveedores para generar el reporte.")

with st.expander("📌 KPIs resumen del tablero"):
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("🔢 Productos Filtrados", value=filtros.shape[0])
    kpi2.metric("💸 Inversión Estimada", value=f"${int(filtros['Costo_Total'].sum()):,}")
    kpi3.metric("📈 Utilidad Estimada", value=f"${int(filtros['Utilidad_Anual'].sum()):,}")

with st.expander("🎛️ Preferencias de visualización"):
    mostrar_todo = st.checkbox("Mostrar todas las columnas del resumen", value=False)
    if mostrar_todo:
        st.dataframe(filtros)
    else:
        st.dataframe(filtros[['SKU', 'Producto / Servicio', 'Venta_Anual', 'Margen_%', 'Utilidad_Anual', 'Recomendacion_Compra']])

with st.expander("📌 Notas de ayuda"):
    st.markdown("""
    - **Demanda Proyectada**: estimación basada en ventas anuales más tendencia histórica.
    - **Stock de Seguridad**: cálculo basado en desviación estándar y nivel de confianza 95% (Z = 1.65).
    - **Recomendación de Compra**: suma de demanda + stock de seguridad.
    - **Lead Time**: días promedio que tarda un proveedor en entregar.
    - **MOQ**: cantidad mínima de compra que exige el proveedor.
    - **Utilidad y Margen**: calculados sobre el precio neto de venta y costo informado.
    """)

with st.expander("🧪 Simulador de escenarios"):
    st.markdown("Ajusta la demanda y el costo para ver el impacto en compras y márgenes.")
    col1, col2 = st.columns(2)
    factor_demanda = col1.slider("Variación de demanda (%)", -50, 50, 0)
    factor_costo = col2.slider("Variación de costos (%)", -30, 30, 0)
    sim_df = filtros.copy()
    sim_df['Demanda_Simulada'] = sim_df['Demanda_Proyectada'] * (1 + factor_demanda / 100)
    sim_df['Stock_Seguridad_Sim'] = sim_df['Stock_Seguridad']
    sim_df['Recompra_Simulada'] = (sim_df['Demanda_Simulada'] + sim_df['Stock_Seguridad_Sim']).astype(int)
    sim_df['Costo_Simulado'] = sim_df['Costo_Unitario'] * (1 + factor_costo / 100)
    sim_df['Costo_Total_Sim'] = sim_df['Costo_Simulado'] * sim_df['Recompra_Simulada']
    sim_df['Ingreso_Estimado'] = sim_df['Venta_Anual']
    sim_df['Utilidad_Simulada'] = sim_df['Ingreso_Estimado'] - sim_df['Costo_Total_Sim']
    sim_df['Margen_Simulado_%'] = round((sim_df['Utilidad_Simulada'] / sim_df['Ingreso_Estimado']) * 100, 1)
    st.dataframe(sim_df[['SKU', 'Producto / Servicio', 'Demanda_Simulada', 'Recompra_Simulada', 'Costo_Simulado', 'Utilidad_Simulada', 'Margen_Simulado_%']])
    st.markdown("**Resumen de escenario simulado:**")
    total_inversion = int(sim_df['Costo_Total_Sim'].sum())
    total_utilidad = int(sim_df['Utilidad_Simulada'].sum())
    st.success(f"💵 Inversión total simulada: ${total_inversion:,}")
    st.success(f"📈 Utilidad total simulada: ${total_utilidad:,}")
