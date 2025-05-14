import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Autenticación con Google Sheets usando credenciales de servicio (almacenadas en st.secrets para seguridad).
# Nota: En un entorno real, st.secrets["gcp_service_account"] contendría las credenciales JSON.
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(credentials)

# Abrir el archivo de Google Sheets por URL o por nombre.
sheet = client.open_by_url(st.secrets["gsheets_url"])  # URL del Google Sheets con las hojas de ventas.

# Obtener todas las hojas cuyo nombre empieza con "ventas_"
worksheets = [ws for ws in sheet.worksheets() if ws.title.startswith("ventas_")]

# Leer y consolidar los datos de cada hoja en una lista de DataFrames.
dataframes = []
for ws in worksheets:
    # Obtener todos los registros de la hoja como una lista de diccionarios
    records = ws.get_all_records()
    df_ws = pd.DataFrame(records)
    # Opcional: agregar columna de año a partir del nombre de la hoja (asumiendo formato 'ventas_AAAA')
    try:
        year = int(ws.title.split('_')[1])
    except:
        year = None
    df_ws['Año'] = year
    dataframes.append(df_ws)

# Concatenar todos los DataFrames en uno solo
ventas_df = pd.concat(dataframes, ignore_index=True)

# Convertir columna de fecha a tipo datetime para facilitar operaciones temporales
ventas_df['Fecha'] = pd.to_datetime(ventas_df['Fecha'])

# Verificar la consolidación
st.write("Datos consolidados de ventas:", ventas_df.shape, "filas")
st.dataframe(ventas_df.head())

# Asegurar que los datos estén ordenados por fecha
ventas_df = ventas_df.sort_values('Fecha')

# Calcular ventas totales y estadísticas mensuales por SKU usando groupby
import numpy as np

# Grupo de datos por SKU y Año para análisis anual
ventas_por_sku_año = ventas_df.groupby(['Año','SKU'])['Venta'].sum().reset_index()

# Tomar el último año disponible (el más reciente) para base de proyección
ultimo_año = ventas_df['Año'].max()

# 1. Demanda proyectada anual por SKU (tomamos ventas del último año como pronóstico del siguiente, ajustable)
proyeccion = {}
ventas_ultimo_año = ventas_por_sku_año[ventas_por_sku_año['Año'] == ultimo_año]
for _, row in ventas_ultimo_año.iterrows():
    sku = row['SKU']
    ventas_anuales = row['Venta']
    # Supongamos una tasa de crecimiento anual promedio calculada a partir de años anteriores (simple ejemplo)
    ventas_hist_sku = ventas_por_sku_año[ventas_por_sku_año['SKU'] == sku]
    if len(ventas_hist_sku) > 1:
        # Calcular tasa de crecimiento promedio anual (CAGR simple entre primer y último año histórico)
        inicio = ventas_hist_sku.iloc[0]['Venta']
        fin = ventas_hist_sku.iloc[-1]['Venta']
        años = ventas_hist_sku['Año'].iloc[-1] - ventas_hist_sku['Año'].iloc[0]
        tasa_crecimiento = ((fin/inicio) ** (1/años) - 1) if años > 0 and inicio > 0 else 0
    else:
        tasa_crecimiento = 0
    # Proyección: última venta anual * (1 + tasa de crecimiento promedio)
    proyeccion[sku] = int(round(ventas_anuales * (1 + tasa_crecimiento)))
    # Si no hay crecimiento histórico (tasa 0), proyección = ventas último año sin cambio.

# 2. Calcular desviación estándar de ventas mensuales por SKU (variabilidad mensual)
desviacion_mensual = ventas_df.groupby('SKU')['Venta'].std().to_dict()

# Definir coeficiente Z para nivel de servicio (95% -> Z=1.65)
Z = 1.65  # 95% de confianza en distribución normal:contentReference[oaicite:1]{index=1}
stock_seguridad = {}
for sku, std in desviacion_mensual.items():
    # Suponemos lead time ~ 1 mes para simplificar, stock de seguridad = Z * desviación mensual
    stock_seguridad[sku] = int(round(Z * std)) if not np.isnan(std) else 0

# 3. Calcular rentabilidad y margen por producto.
# Supongamos que tenemos un diccionario de costo unitario por SKU (en una app real vendría de datos).
costos_unitarios = {
    "SKU001": 50, "SKU002": 60, "SKU003": 70, "SKU004": 80, "SKU005": 90
}
# Calcular ventas totales y unidades por SKU en el último año (asumimos 'Venta' está en unidades vendidas o ingresos).
resumen_sku = ventas_df[ventas_df['Año'] == ultimo_año].groupby(['SKU','Producto/Servicio']).agg(
    Venta_Anual=('Venta','sum')
).reset_index()

# Añadir columna de Utilidad (Rentabilidad) y Margen
utilidades = []
margenes = []
for _, row in resumen_sku.iterrows():
    sku = row['SKU']
    ingresos = row['Venta_Anual']            # supuestos ingresos totales de ventas para el último año
    costo_unit = costos_unitarios.get(sku, 0)
    # Asumimos que 'Venta' representa ingresos por 1 unidad * cantidad vendida. Sin datos de cantidad, supondremos 1 unidad = 1 venta.
    # Para propósitos de ejemplo, estimemos cantidad vendida = ingresos / costo_unit (esto asume precio ~ costo, solo para demo).
    cantidad_vendida = ingresos / costo_unit if costo_unit else 0
    costo_total = costo_unit * cantidad_vendida
    utilidad = ingresos - costo_total  # ganancia total
    margen = utilidad / ingresos if ingresos != 0 else 0  # porcentaje de margen sobre ingresos
    utilidades.append(utilidad)
    margenes.append(margen)

resumen_sku['Utilidad_Anual'] = utilidades
resumen_sku['Margen_%'] = [round(m*100, 1) for m in margenes]

# 4. Recomendaciones de compra anuales (lógica básica: proyección + stock seguridad)
recomendaciones = []
for _, row in resumen_sku.iterrows():
    sku = row['SKU']
    dem_proj = proyeccion.get(sku, 0)
    ss = stock_seguridad.get(sku, 0)
    recom = dem_proj + ss
    recomendaciones.append(recom)

resumen_sku['Recomendacion_Compra'] = recomendaciones

# Mostrar el resumen calculado por SKU para ver resultados
st.write("Resumen de métricas por SKU (último año):")
st.dataframe(resumen_sku)

# SIDEBAR FILTERS (opcionalmente, usar st.sidebar para ubicarlos aparte)
st.sidebar.header("Filtros:")
margen_min = st.sidebar.slider("Margen mínimo (%)", min_value=0, max_value=100, value=0)
util_min = st.sidebar.number_input("Utilidad mínima anual", value=0, step=1000)
venta_min = st.sidebar.number_input("Ventas anuales mínimas", value=0, step=1000)

# Filtrar el resumen de SKU según los criterios
filtered_sku_df = resumen_sku[
    (resumen_sku['Margen_%'] >= margen_min) &
    (resumen_sku['Utilidad_Anual'] >= util_min) &
    (resumen_sku['Venta_Anual'] >= venta_min)
]

st.write(f"Productos que cumplen filtros: {filtered_sku_df.shape[0]} / {resumen_sku.shape[0]}")
st.dataframe(filtered_sku_df)

# Selección de nivel de agrupación para visualizar ventas mensuales
nivel_opciones = ["Tipo", "Producto/Servicio", "SKU", "Variante"]
nivel = st.selectbox("Agrupar ventas mensuales por:", options=nivel_opciones, index=2)  # default SKU

# Filtrar los datos históricos originales a solo los SKU seleccionados tras filtros
skus_filtrados = filtered_sku_df['SKU'].tolist()
datos_filtrados = ventas_df[ventas_df['SKU'].isin(skus_filtrados)]

# Agregar columna 'Mes' para agrupar fácilmente por mes (año-mes)
datos_filtrados['Mes'] = datos_filtrados['Fecha'].dt.to_period('M')  # período mensual

# Agrupar ventas mensuales según el nivel seleccionado
if nivel == "Tipo":
    grupo = "Tipo"  # asumiendo columna 'Tipo' indica categoría general
elif nivel == "Producto/Servicio":
    grupo = "Producto/Servicio"
elif nivel == "SKU":
    grupo = "SKU"
elif nivel == "Variante":
    grupo = "Variante"
    
ventas_mensuales = datos_filtrados.groupby([grupo, 'Mes'])['Venta'].sum().reset_index()

# Si no hay datos filtrados, advertir
if ventas_mensuales.empty:
    st.write("No hay datos para los filtros seleccionados.")
else:
    st.write(f"Ventas mensuales agrupadas por **{nivel}**:")
    # Pivotear para formato amplio (filas=Mes, columnas=grupo) para gráfica más fácil
    ventas_pivot = ventas_mensuales.pivot(index='Mes', columns=grupo, values='Venta').fillna(0)
    # Ordenar por fecha
    ventas_pivot = ventas_pivot.sort_index()
    # Mostrar tabla pivote como referencia
    st.dataframe(ventas_pivot.head())

    # Graficar las series de ventas mensuales
    st.line_chart(ventas_pivot)

# Preparar DataFrame para la orden de compra con los productos filtrados
orden_df = filtered_sku_df.copy()
# Seleccionar columnas relevantes y renombrar para claridad en la tabla
orden_df = orden_df[['SKU', 'Producto/Servicio', 'Venta_Anual', 'Recomendacion_Compra']]
orden_df = orden_df.rename(columns={'Venta_Anual': 'Ventas Últ. Año', 'Recomendacion_Compra': 'Cant. Recomendada'})

# Añadir columna booleana 'Incluir' inicialmente False
orden_df['Incluir'] = False

st.write("Seleccione productos y ajuste cantidades para la orden de compra:")
# Mostrar editor de tabla interactivo
edited_df = st.data_editor(
    orden_df,
    column_config={ "Incluir": st.column_config.CheckboxColumn("Incluir en orden") },
    num_rows="dynamic"
)

# Filtrar los productos seleccionados (Incluir == True)
productos_seleccionados = edited_df[edited_df['Incluir'] == True]

st.write(f"Productos seleccionados para orden: {productos_seleccionados.shape[0]}")
st.dataframe(productos_seleccionados)

# Remover la columna 'Incluir' para el archivo de salida
output_df = productos_seleccionados.drop(columns=['Incluir']).copy()

# Botón para descargar en CSV
csv_data = output_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Descargar orden en CSV",
    data=csv_data,
    file_name="orden_de_compra.csv",
    mime="text/csv"
)

# Botón para descargar en Excel
import io
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    output_df.to_excel(writer, index=False, sheet_name="OrdenCompra")
    writer.save()
excel_data = output.getvalue()
st.download_button(
    label="Descargar orden en Excel",
    data=excel_data,
    file_name="orden_de_compra.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# 1. Gráfico de Barras - Top 5 productos más rentables (mayor utilidad anual)
top_rentables = resumen_sku.nlargest(5, 'Utilidad_Anual')
st.write("Top 5 Productos por Utilidad Anual:")
if not top_rentables.empty:
    import altair as alt
    chart_bar = alt.Chart(top_rentables).mark_bar(color='#4e8cf5').encode(
        x=alt.X('Producto/Servicio:N', sort='-y', title='Producto'),
        y=alt.Y('Utilidad_Anual:Q', title='Utilidad Anual'),
        tooltip=['SKU', 'Producto/Servicio', 'Utilidad_Anual', 'Margen_%']
    )
    st.altair_chart(chart_bar, use_container_width=True)
else:
    st.write("No hay datos de utilidad para mostrar.")

# 2. Gráfico de Dispersión - Margen vs Volumen de Ventas (ventas anuales)
st.write("Relación entre Margen (%) y Volumen de Ventas:")
if not resumen_sku.empty:
    chart_scatter = alt.Chart(resumen_sku).mark_circle(size=60, opacity=0.7).encode(
        x=alt.X('Venta_Anual:Q', title='Ventas Anuales'),
        y=alt.Y('Margen_%:Q', title='Margen %'),
        color=alt.condition(
            alt.datum.Margen_% > margen_min, alt.value('orange'), alt.value('gray')
        ),  # destacar en naranja los que cumplen el filtro de margen, gris los demás
        tooltip=['SKU', 'Producto/Servicio', 'Venta_Anual', 'Margen_%', 'Utilidad_Anual']
    ).interactive()
    st.altair_chart(chart_scatter, use_container_width=True)
else:
    st.write("No hay datos para dispersión.")
