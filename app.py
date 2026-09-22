import streamlit as st
import zipfile
import os
import time
import rasterio
from rasterio.transform import rowcol
from shapely.geometry import Point
import geopandas as gpd
from pyproj import Transformer
import numpy as np
from datetime import datetime

# Configuración inicial de la página web (Optimizada para PC/Laptop)
st.set_page_config(
    page_title="Syntro - Motor Geoespacial SAR",
    page_icon="🌍",
    layout="centered"
)

# Base de datos agronómica de Syntro
FAO_KC_DB = {
    "Café": {"ini": 0.90, "mid": 1.05, "end": 0.95, "rvi_min": 0.25, "rvi_max": 0.75},
    "Cacao": {"ini": 0.95, "mid": 1.15, "end": 1.00, "rvi_min": 0.30, "rvi_max": 0.80},
    "Lechosa (Papaya)": {"ini": 0.50, "mid": 1.10, "end": 0.80, "rvi_min": 0.15, "rvi_max": 0.65},
    "Cebolla": {"ini": 0.70, "mid": 1.05, "end": 0.75, "rvi_min": 0.12, "rvi_max": 0.55},
    "Soja": {"ini": 0.40, "mid": 1.15, "end": 0.50, "rvi_min": 0.15, "rvi_max": 0.70},
    "Sorgo": {"ini": 0.30, "mid": 1.00, "end": 0.55, "rvi_min": 0.12, "rvi_max": 0.65},
    "Maíz": {"ini": 0.30, "mid": 1.20, "end": 0.60, "rvi_min": 0.15, "rvi_max": 0.75},
    "Tomate": {"ini": 0.60, "mid": 1.15, "end": 0.80, "rvi_min": 0.20, "rvi_max": 0.68},
    "Melón": {"ini": 0.50, "mid": 1.05, "end": 0.75, "rvi_min": 0.15, "rvi_max": 0.60},
    "Patilla (Sandía)": {"ini": 0.40, "mid": 1.05, "end": 0.75, "rvi_min": 0.15, "rvi_max": 0.60},
    "Pasto (Pradera)": {"ini": 0.40, "mid": 0.85, "end": 0.80, "rvi_min": 0.18, "rvi_max": 0.72}
}

# Barra Lateral con Branding Institucional (icon.png)
with st.sidebar:
    if os.path.exists("icon.png"):
        st.image("icon.png", width=120)
    st.markdown("### **SYNTRO INICIATIVA**")
    st.markdown("Plataforma de Teledetección y Analítica Bio-financiera.")
    st.markdown("---")
    st.info("💡 **Modo PC/Laptop Activo:** Procesamiento optimizado de imágenes SAR para estaciones de trabajo.")

# Cabecera Visual Principal
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("icon.png"):
        st.image("icon.png", width=80)
with col_title:
    st.title("CALIBRACIÓN DINÁMICA DE KC (SAR)")
    st.markdown("**Motor Geoespacial para Monitoreo de Cultivos**")

st.markdown("---")

# 1. Carga del archivo ZIP de Sentinel-1
st.subheader("1. Archivo de Radar Copernicus Sentinel-1 (ZIP)")
uploaded_zip = st.file_uploader("Selecciona el archivo ZIP de Sentinel-1", type=["zip"])

# 2. Selección de Cultivo y Fecha
col1, col2 = st.columns(2)
with col1:
    st.subheader("2. Cultivo Objetivo")
    cultivo_sel = st.selectbox("Seleccione el cultivo", list(FAO_KC_DB.keys()), index=0) # Predeterminado: Café

with col2:
    st.subheader("3. Anclaje Fenológico")
    fecha_ref = st.date_input("Fecha de Referencia / Inicio de Ciclo", datetime.now())

# 3. Ubicación (Coordenadas Manuales o Shapefile)
st.subheader("4. Ubicación del Punto de Evaluación")
modo_ubicacion = st.radio("Método de entrada de ubicación:", ["Coordenadas Manuales (WGS84)", "Shapefile (.shp comprimido en .zip)"])

lon, lat = -71.500, 10.500 # Valores por defecto
shape_file_uploaded = None

if modo_ubicacion == "Coordenadas Manuales (WGS84)":
    col_lon, col_lat = st.columns(2)
    with col_lon:
        lon = st.number_input("Longitud (X)", value=-71.500, format="%.6f")
    with col_lat:
        lat = st.number_input("Latitud (Y)", value=10.500, format="%.6f")
else:
    shape_file_uploaded = st.file_uploader("Cargue el archivo Shapefile (.zip que contenga .shp, .shx, .dbf)", type=["zip"])

st.markdown("---")

# 4. Botón de Ejecución
if st.button("EJECUTAR CÁLCULO Y GENERAR INFORME", type="primary"):
    if not uploaded_zip:
        st.warning("⚠️ Debe cargar obligatoriamente el archivo ZIP de Sentinel-1.")
    else:
        with st.status("Ejecutando motor geoespacial Syntro...", expanded=True) as status:
            try:
                # Guardar ZIP de S1 temporalmente
                temp_dir = "./temp_syntro"
                os.makedirs(temp_dir, exist_ok=True)
                zip_path_local = os.path.join(temp_dir, uploaded_zip.name)
                
                with open(zip_path_local, "wb") as f:
                    f.write(uploaded_zip.getbuffer())
                
                st.write("📂 Extrayendo bandas VV y VH del radar...")
                with zipfile.ZipFile(zip_path_local, 'r') as zf:
                    namelist = zf.namelist()
                    vv_file = [n for n in namelist if 'measurement' in n and 'vv' in n.lower() and n.endswith('.tiff')][0]
                    vh_file = [n for n in namelist if 'measurement' in n and 'vh' in n.lower() and n.endswith('.tiff')][0]
                    vv_ext = zf.extract(vv_file, path=temp_dir)
                    vh_ext = zf.extract(vh_file, path=temp_dir)

                # Manejo de coordenadas si es Shapefile
                if modo_ubicacion == "Shapefile (.shp comprimido en .zip)":
                    if shape_file_uploaded:
                        shp_zip_path = os.path.join(temp_dir, shape_file_uploaded.name)
                        with open(shp_zip_path, "wb") as f:
                            f.write(shape_file_uploaded.getbuffer())
                        with zipfile.ZipFile(shp_zip_path, 'r') as szf:
                            szf.extractall(temp_dir)
                        shp_path = [os.path.join(temp_dir, f) for f in szf.namelist() if f.endswith('.shp')][0]
                        gdf = gpd.read_file(shp_path).to_crs("EPSG:4326")
                        geom = gdf.geometry.iloc[0]
                        if geom.geom_type in ['Polygon', 'MultiPolygon']:
                            p_cent = geom.centroid
                            lon, lat = p_cent.x, p_cent.y
                        else:
                            lon, lat = geom.x, geom.y
                    else:
                        st.error("Debe cargar el archivo ZIP del Shapefile.")
                        st.stop()

                st.write(f"📍 Coordenadas fijadas -> Lon: {lon:.4f}, Lat: {lat:.4f}")

                # Extracción de valores en los rasters
                st.write("🛰️ Leyendo valores de retrodispersión en los píxeles...")
                with rasterio.open(vv_ext) as src_vv:
                    p_gdf = gpd.GeoDataFrame(index=[1], geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(src_vv.crs)
                    rx, ry = p_gdf.geometry.iloc[0].x, p_gdf.geometry.iloc[0].y
                    row, col = rowcol(src_vv.transform, rx, ry)
                    val_vv_db = src_vv.read(1)[row, col]

                with rasterio.open(vh_ext) as src_vh:
                    val_vh_db = src_vh.read(1)[row, col]

                # Cálculo de RVI y Kc
                vv_lin = 10 ** (val_vv_db / 10.0)
                vh_lin = 10 ** (val_vh_db / 10.0)
                den = vv_lin + vh_lin
                rvi = (4.0 * vh_lin) / den if den != 0 else 0.0

                params = FAO_KC_DB[cultivo_sel]
                rvi_min, rvi_max = params["rvi_min"], params["rvi_max"]
                factor_escala = max(0.0, min(1.0, (rvi - rvi_min) / (rvi_max - rvi_min)))
                kc_calculado = params["ini"] + (params["mid"] - params["ini"]) * factor_escala

                # Limpieza de archivos temporales tiff
                if os.path.exists(vv_ext): os.remove(vv_ext)
                if os.path.exists(vh_ext): os.remove(vh_ext)

                status.update(label="¡Proceso completado con éxito!", state="complete", expanded=False)

            except Exception as e:
                st.error(f"Error crítico en el motor: {str(e)}")
                st.stop()

        # Resultados en Pantalla
        st.success("Cálculo finalizado correctamente.")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Cultivo Seleccionado", cultivo_sel)
        m2.metric("Índice RVI (Radar)", f"{rvi:.4f}")
        m3.metric("Kc Dinámico Local", f"{kc_calculado:.2f}")

        # Generación de HTML descargable
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe Técnico Syntro - Kc Dinámico (SAR)</title>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f6f7; color: #2c3e50; margin: 0; padding: 20px; }}
        .container {{ max-width: 800px; background: #ffffff; margin: auto; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; border-bottom: 3px solid #1b4f72; padding-bottom: 15px; margin-bottom: 20px; }}
        .header h1 {{ color: #1b4f72; margin: 0; font-size: 22px; }}
        .section-title {{ background: #2980b9; color: white; padding: 8px 12px; font-size: 15px; border-radius: 4px; margin-top: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 14px; }}
        th {{ background-color: #f8f9fa; color: #2c3e50; }}
        .highlight {{ background-color: #e8f8f5; font-weight: bold; color: #117a65; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #95a5a6; border-top: 1px solid #eee; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>INFORME TÉCNICO SYNTRO</h1>
            <p>Teledetección SAR & Coeficiente de Cultivo Adaptado al Trópico</p>
        </div>
        <div class="section-title">1. Datos Generales de la Evaluación</div>
        <table>
            <tr><th>Parámetro</th><th>Valor Registrado</th></tr>
            <tr><td>Cultivo Analizado</td><td><b>{cultivo_sel}</b></td></tr>
            <tr><td>Fecha de Referencia</td><td>{fecha_ref.strftime('%Y-%m-%d')}</td></tr>
            <tr><td>Ubicación (Lon, Lat)</td><td>{lon:.4f}, {lat:.4f}</td></tr>
            <tr><td>Fecha de Emisión</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        <div class="section-title">2. Métricas Físicas de Radar (Sentinel-1 SAR)</div>
        <table>
            <tr><th>Variable</th><th>Valor</th></tr>
            <tr><td>Retrodispersión Banda VV</td><td>{val_vv_db:.2f} dB</td></tr>
            <tr><td>Retrodispersión Banda VH</td><td>{val_vh_db:.2f} dB</td></tr>
            <tr><td>Índice de Vegetación de Radar (RVI)</td><td><b>{rvi:.4f}</b></td></tr>
        </table>
        <div class="section-title">3. Resultado del Coeficiente de Cultivo (Kc Local)</div>
        <table>
            <tr class="highlight"><td>Kc Dinámico Calculado</td><td>{kc_calculado:.2f}</td></tr>
        </table>
        <div class="footer"><p>Generado por el motor agrotecnológico Syntro.</p></div>
    </div>
</body>
</html>
"""

        html_filename = f"Informe_Syntro_{cultivo_sel.replace(' ', '_')}.html"
        st.download_button(
            label="📥 Descargar Informe Técnico en HTML",
            data=html_content,
            file_name=html_filename,
            mime="text/html"
        )