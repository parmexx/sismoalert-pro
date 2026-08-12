import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import math
import numpy as np
import streamlit.components.v1 as components
import base64, os
from streamlit_geolocation import streamlit_geolocation
from analytics import (
    calcular_b_value, curva_gutenberg_richter,
    detectar_anomalias, calcular_tendencia,
    calcular_score, guardar_registro, cargar_historial,
)

st.set_page_config(
    page_title="SismoAlert Pro",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════════════════════
# ESTILOS PREMIUM
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Fondo principal — imagen se inyecta por Python */
.stApp {
    background: #0a0a0f;
}
.stApp.has-bg-image {
    background-size: cover !important;
    background-position: center !important;
    background-attachment: fixed !important;
    background-repeat: no-repeat !important;
}

/* Orbes de fondo */
.orb {
    position: fixed;
    border-radius: 50%;
    filter: blur(80px);
    pointer-events: none;
    z-index: 0;
    animation: orb-float ease-in-out infinite alternate;
}
.orb-1 {
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(255,40,40,0.25) 0%, transparent 70%);
    top: -150px; left: -100px;
    animation-duration: 12s;
}
.orb-2 {
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(255,100,0,0.18) 0%, transparent 70%);
    top: 30%; right: -80px;
    animation-duration: 16s;
    animation-delay: -4s;
}
.orb-3 {
    width: 450px; height: 450px;
    background: radial-gradient(circle, rgba(180,0,0,0.20) 0%, transparent 70%);
    bottom: -100px; left: 35%;
    animation-duration: 14s;
    animation-delay: -8s;
}
.orb-4 {
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(255,60,60,0.15) 0%, transparent 70%);
    top: 55%; left: 20%;
    animation-duration: 18s;
    animation-delay: -2s;
}
@keyframes orb-float {
    0%   { transform: translate(0px, 0px)   scale(1);    opacity: 0.6; }
    33%  { transform: translate(30px, -20px) scale(1.08); opacity: 1;   }
    66%  { transform: translate(-20px, 15px) scale(0.95); opacity: 0.8; }
    100% { transform: translate(15px, 25px)  scale(1.04); opacity: 0.9; }
}

/* Canvas de partículas */
#seismic-bg {
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    z-index: 0;
    pointer-events: none;
    opacity: 0.3;
}
.stApp > * { position: relative; z-index: 1; }
section[data-testid="stSidebar"] { z-index: 10 !important; }
header { z-index: 10 !important; }

/* Sidebar scrollable */
section[data-testid="stSidebar"] > div {
    overflow-y: auto !important;
    height: 100vh;
}
section[data-testid="stSidebar"] .block-container {
    padding-bottom: 2rem;
}

/* Header principal */
.hero-header {
    background: linear-gradient(135deg, #1a0000 0%, #2d0000 40%, #1a0a00 100%);
    border: 1px solid rgba(255,75,75,0.3);
    border-radius: 20px;
    padding: 2.5rem 2rem;
    text-align: center;
    margin-bottom: 2rem;
    box-shadow: 0 0 60px rgba(255,75,75,0.15), inset 0 1px 0 rgba(255,255,255,0.05);
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle, rgba(255,75,75,0.05) 0%, transparent 60%);
    animation: pulse-bg 4s ease-in-out infinite;
}
@keyframes pulse-bg {
    0%, 100% { transform: scale(1); opacity: 0.5; }
    50% { transform: scale(1.1); opacity: 1; }
}
.hero-title {
    font-size: 3rem; font-weight: 900;
    background: linear-gradient(135deg, #FF4B4B, #FF8C00, #FF4B4B);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0; letter-spacing: -1px;
}
.hero-subtitle {
    color: rgba(255,255,255,0.5); font-size: 1rem;
    margin-top: 0.5rem; font-weight: 300; letter-spacing: 2px;
    text-transform: uppercase;
}

/* Tarjetas métricas glassmorphism */
.glass-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    backdrop-filter: blur(20px);
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.glass-card:hover {
    border-color: rgba(255,75,75,0.3);
    box-shadow: 0 8px 32px rgba(255,75,75,0.1);
    transform: translateY(-2px);
}
.glass-card .metric-value {
    font-size: 2.2rem; font-weight: 900;
    background: linear-gradient(135deg, #FF4B4B, #FF8C00);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.glass-card .metric-label {
    color: rgba(255,255,255,0.4); font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 1.5px; margin-top: 0.25rem;
}

/* Alerta sísmica */
.alert-critica {
    background: linear-gradient(135deg, rgba(255,0,0,0.15), rgba(255,75,75,0.05));
    border: 1px solid rgba(255,0,0,0.5);
    border-radius: 12px; padding: 1.2rem 1.5rem;
    animation: blink-border 1.5s ease-in-out infinite;
}
@keyframes blink-border {
    0%, 100% { border-color: rgba(255,0,0,0.5); box-shadow: 0 0 0 rgba(255,0,0,0); }
    50% { border-color: rgba(255,0,0,1); box-shadow: 0 0 20px rgba(255,0,0,0.3); }
}
.alert-alto {
    background: rgba(255,75,75,0.08);
    border: 1px solid rgba(255,75,75,0.4);
    border-radius: 12px; padding: 1.2rem 1.5rem;
}
.alert-medio {
    background: rgba(255,165,0,0.08);
    border: 1px solid rgba(255,165,0,0.4);
    border-radius: 12px; padding: 1.2rem 1.5rem;
}
.alert-bajo {
    background: rgba(0,204,68,0.08);
    border: 1px solid rgba(0,204,68,0.4);
    border-radius: 12px; padding: 1.2rem 1.5rem;
}

/* Tarjeta plan de acción */
.plan-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1rem 1.5rem;
    margin: 0.5rem 0;
}
.plan-step {
    display: flex; align-items: center; gap: 0.75rem;
    color: rgba(255,255,255,0.8); padding: 0.4rem 0;
    font-size: 0.9rem;
}

/* Badge de tsunami */
.tsunami-badge {
    background: linear-gradient(135deg, #003366, #0066cc);
    border: 1px solid #0099ff;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    color: #66ccff;
    font-weight: 600;
    display: inline-block;
    margin: 0.25rem;
}

/* Tabs personalizados */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(255,255,255,0.02);
    border-radius: 12px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: rgba(255,255,255,0.5);
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: rgba(255,75,75,0.2) !important;
    color: #FF4B4B !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0d1a 0%, #0a0a0f 100%);
    border-right: 1px solid rgba(255,255,255,0.05);
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,75,75,0.3); border-radius: 2px; }

/* Onda sísmica */
.wave-container {
    width: 100%; height: 80px;
    margin-top: 1rem; overflow: hidden;
}
.seismic-wave { width: 100%; height: 80px; }

/* Ticker de noticias */
.ticker-wrapper {
    background: rgba(255,75,75,0.08);
    border: 1px solid rgba(255,75,75,0.25);
    border-radius: 10px;
    overflow: hidden;
    padding: 0.6rem 0;
    margin-bottom: 1.5rem;
    display: flex; align-items: center;
}
.ticker-label {
    background: #FF4B4B;
    color: white; font-weight: 700;
    font-size: 0.75rem; letter-spacing: 1px;
    padding: 0.35rem 0.9rem;
    border-radius: 6px; margin: 0 1rem;
    white-space: nowrap; flex-shrink: 0;
}
.ticker-track {
    overflow: hidden; flex: 1;
}
.ticker-content {
    display: inline-block;
    white-space: nowrap;
    animation: ticker-scroll 150s linear infinite;
    color: rgba(255,255,255,0.75);
    font-size: 0.85rem;
}
@keyframes ticker-scroll {
    0%   { transform: translateX(0%); }
    100% { transform: translateX(-50%); }
}
.ticker-item { margin: 0 2.5rem; }
.ticker-mag-high   { color: #FF4B4B; font-weight: 700; }
.ticker-mag-medium { color: #FF8C00; font-weight: 600; }
.ticker-mag-low    { color: #ADFF2F; }

/* Contadores animados */
@keyframes count-up {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
.glass-card { animation: count-up 0.6s ease forwards; }
.glass-card:nth-child(2) { animation-delay: 0.1s; }
.glass-card:nth-child(3) { animation-delay: 0.2s; }
.glass-card:nth-child(4) { animation-delay: 0.3s; }
.glass-card:nth-child(5) { animation-delay: 0.4s; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════
REGIONES = {
    "🌎 Todo el mundo": {},
    "🇨🇴 Colombia": {"minlatitude": -4, "maxlatitude": 13, "minlongitude": -79, "maxlongitude": -66},
    "🇲🇽 México": {"minlatitude": 14, "maxlatitude": 33, "minlongitude": -118, "maxlongitude": -86},
    "🇵🇪 Perú": {"minlatitude": -18, "maxlatitude": 0, "minlongitude": -82, "maxlongitude": -68},
    "🇨🇱 Chile": {"minlatitude": -56, "maxlatitude": -17, "minlongitude": -76, "maxlongitude": -65},
    "🇪🇨 Ecuador": {"minlatitude": -5, "maxlatitude": 2, "minlongitude": -82, "maxlongitude": -75},
    "🇦🇷 Argentina": {"minlatitude": -56, "maxlatitude": -21, "minlongitude": -74, "maxlongitude": -53},
    "🇧🇷 Brasil": {"minlatitude": -34, "maxlatitude": 6, "minlongitude": -74, "maxlongitude": -34},
    "🇨🇷 Costa Rica": {"minlatitude": 8, "maxlatitude": 12, "minlongitude": -86, "maxlongitude": -82},
    "🇵🇦 Panamá": {"minlatitude": 7, "maxlatitude": 10, "minlongitude": -83, "maxlongitude": -77},
    "🇺🇸 Estados Unidos": {"minlatitude": 24, "maxlatitude": 50, "minlongitude": -126, "maxlongitude": -66},
    "🇺🇸 California": {"minlatitude": 32, "maxlatitude": 42, "minlongitude": -125, "maxlongitude": -114},
    "🇨🇦 Canadá": {"minlatitude": 41, "maxlatitude": 84, "minlongitude": -141, "maxlongitude": -52},
    "🇯🇵 Japón": {"minlatitude": 30, "maxlatitude": 46, "minlongitude": 129, "maxlongitude": 146},
    "🇹🇭 Tailandia": {"minlatitude": 5, "maxlatitude": 21, "minlongitude": 97, "maxlongitude": 106},
    "🇮🇩 Indonesia": {"minlatitude": -11, "maxlatitude": 6, "minlongitude": 95, "maxlongitude": 141},
    "🇵🇭 Filipinas": {"minlatitude": 4, "maxlatitude": 22, "minlongitude": 116, "maxlongitude": 127},
    "🇹🇼 Taiwán": {"minlatitude": 21, "maxlatitude": 26, "minlongitude": 119, "maxlongitude": 123},
    "🇨🇳 China": {"minlatitude": 18, "maxlatitude": 54, "minlongitude": 73, "maxlongitude": 135},
    "🇰🇷 Corea del Sur": {"minlatitude": 33, "maxlatitude": 39, "minlongitude": 124, "maxlongitude": 130},
    "🇳🇿 Nueva Zelanda": {"minlatitude": -48, "maxlatitude": -34, "minlongitude": 165, "maxlongitude": 179},
    "🇦🇺 Australia": {"minlatitude": -44, "maxlatitude": -10, "minlongitude": 112, "maxlongitude": 154},
    "🇮🇳 India": {"minlatitude": 6, "maxlatitude": 36, "minlongitude": 68, "maxlongitude": 98},
    "🇳🇵 Nepal": {"minlatitude": 26, "maxlatitude": 31, "minlongitude": 80, "maxlongitude": 89},
    "🇹🇷 Turquía": {"minlatitude": 35, "maxlatitude": 43, "minlongitude": 25, "maxlongitude": 45},
    "🇮🇹 Italia": {"minlatitude": 36, "maxlatitude": 47, "minlongitude": 6, "maxlongitude": 19},
    "🇬🇷 Grecia": {"minlatitude": 34, "maxlatitude": 42, "minlongitude": 19, "maxlongitude": 29},
    "🇪🇸 España": {"minlatitude": 35, "maxlatitude": 44, "minlongitude": -10, "maxlongitude": 4},
    "🇵🇹 Portugal": {"minlatitude": 36, "maxlatitude": 43, "minlongitude": -10, "maxlongitude": -6},
    "🇮🇸 Islandia": {"minlatitude": 63, "maxlatitude": 67, "minlongitude": -25, "maxlongitude": -13},
    "🇳🇴 Noruega": {"minlatitude": 57, "maxlatitude": 72, "minlongitude": 4, "maxlongitude": 32},
    "🇮🇳 Indonesia": {"minlatitude": -11, "maxlatitude": 6, "minlongitude": 95, "maxlongitude": 141},
    "🇵🇬 Papúa Nueva Guinea": {"minlatitude": -12, "maxlatitude": 0, "minlongitude": 140, "maxlongitude": 160},
    "🇸🇧 Islas Salomón": {"minlatitude": -13, "maxlatitude": -5, "minlongitude": 155, "maxlongitude": 170},
    "🇻🇺 Vanuatu": {"minlatitude": -21, "maxlatitude": -13, "minlongitude": 166, "maxlongitude": 171},
    "🇫🇯 Fiyi": {"minlatitude": -21, "maxlatitude": -15, "minlongitude": 176, "maxlongitude": 180},
    "🇸🇨 Islas Seychelles": {"minlatitude": -5, "maxlatitude": -3, "minlongitude": 46, "maxlongitude": 56},
    "🇿🇦 Sudáfrica": {"minlatitude": -35, "maxlatitude": -22, "minlongitude": 16, "maxlongitude": 33},
    "🇲🇦 Marruecos": {"minlatitude": 27, "maxlatitude": 36, "minlongitude": -14, "maxlongitude": -1},
    "🇰🇪 Kenia": {"minlatitude": -5, "maxlatitude": 5, "minlongitude": 33, "maxlongitude": 42},
    "🇪🇬 Egipto": {"minlatitude": 22, "maxlatitude": 32, "minlongitude": 24, "maxlongitude": 37},
}

# Centro geográfico de cada región para centrar el mapa automáticamente
REGION_CENTRO = {
    "🌎 Todo el mundo": (20, 0, 2),
    "🇨🇴 Colombia": (4.5, -74.0, 5), "🇲🇽 México": (23.0, -102.0, 5),
    "🇵🇪 Perú": (-9.0, -75.0, 5), "🇨🇱 Chile": (-35.0, -71.0, 5),
    "🇪🇨 Ecuador": (-1.5, -78.0, 6), "🇦🇷 Argentina": (-38.4, -63.6, 4),
    "🇧🇷 Brasil": (-10.0, -52.0, 4), "🇯🇵 Japón": (37.5, 137.5, 5),
    "🇹🇭 Tailandia": (15.0, 101.0, 5), "🇮🇩 Indonesia": (-2.0, 118.0, 4),
    "🇵🇭 Filipinas": (12.0, 122.0, 5), "🇨🇳 China": (35.0, 103.0, 4),
    "🇰🇷 Corea del Sur": (36.5, 127.8, 6), "🇳🇿 Nueva Zelanda": (-41.0, 174.0, 5),
    "🇦🇺 Australia": (-25.0, 134.0, 4), "🇮🇳 India": (22.0, 79.0, 4),
    "🇹🇷 Turquía": (39.0, 35.0, 5), "🇮🇹 Italia": (42.5, 12.5, 5),
    "🇬🇷 Grecia": (39.0, 22.0, 6), "🇪🇸 España": (40.0, -4.0, 5),
    "🇺🇸 Estados Unidos": (39.0, -98.0, 4), "🇨🇦 Canadá": (56.0, -106.0, 4),
    "🇺🇸 California": (37.0, -120.0, 6),
}

CIUDADES_REF = {
    "📍 Montería, Colombia": (8.7575, -75.8814),
    "Bogotá, Colombia": (4.711, -74.072),
    "Medellín, Colombia": (6.244, -75.574),
    "Cali, Colombia": (3.451, -76.532),
    "Barranquilla, Colombia": (10.9685, -74.7813),
    "Cartagena, Colombia": (10.3910, -75.4794),
    "Sincelejo, Colombia": (9.3047, -75.3978),
    "Valledupar, Colombia": (10.4631, -73.2532),
    "Santa Marta, Colombia": (11.2408, -74.1990),
    "Bucaramanga, Colombia": (7.1193, -73.1227),
    "Ciudad de México": (19.433, -99.133),
    "Lima, Perú": (-12.046, -77.043),
    "Santiago, Chile": (-33.457, -70.648),
    "Quito, Ecuador": (-0.180, -78.468),
    "Bangkok, Tailandia": (13.7563, 100.5018),
    "Chiang Mai, Tailandia": (18.7883, 98.9853),
    "Phuket, Tailandia": (7.8804, 98.3923),
    "Tokio, Japón": (35.6762, 139.6503),
    "Manila, Filipinas": (14.5995, 120.9842),
    "Yakarta, Indonesia": (-6.2088, 106.8456),
    "Seúl, Corea del Sur": (37.5665, 126.9780),
    "Personalizada": None,
}

PLAN_ACCION = {
    "CRÍTICO": {
        "color": "alert-critica",
        "icono": "🚨",
        "titulo": "RIESGO CRÍTICO — Acción inmediata requerida",
        "pasos": [
            "🏃 Evacúa a espacios abiertos alejados de edificios",
            "📞 Llama al número de emergencias de tu país",
            "🎒 Ten listo el kit de emergencia (agua, linterna, documentos, medicamentos)",
            "📻 Sintoniza radio de emergencias para instrucciones oficiales",
            "🚫 No uses el ascensor ni enciendas fósforos (riesgo de gas)",
            "⚠️ Aléjate de la costa si estás en zona costera (riesgo de tsunami)",
        ]
    },
    "ALTO": {
        "color": "alert-alto",
        "icono": "🔴",
        "titulo": "RIESGO ALTO — Mantén precaución",
        "pasos": [
            "🎒 Verifica que tu kit de emergencia esté completo y accesible",
            "🏠 Identifica los puntos seguros en tu hogar (bajo mesa sólida, marcos de puertas)",
            "📱 Guarda números de emergencia en tu teléfono",
            "🗺️ Conoce la ruta de evacuación de tu edificio o barrio",
            "💧 Ten reserva de agua potable (mínimo 3 litros por persona/día)",
        ]
    },
    "MEDIO": {
        "color": "alert-medio",
        "icono": "🟠",
        "titulo": "RIESGO MODERADO — Mantente informado",
        "pasos": [
            "📱 Activa notificaciones sísmicas en tu teléfono",
            "🏠 Asegura objetos pesados que puedan caer en un sismo",
            "💊 Ten un botiquín básico en casa",
            "👨‍👩‍👧 Comparte un plan familiar de emergencia",
            "📻 Conoce la frecuencia de la radio de emergencias local",
        ]
    },
    "BAJO": {
        "color": "alert-bajo",
        "icono": "🟢",
        "titulo": "RIESGO BAJO — Zona tranquila",
        "pasos": [
            "✅ No se registró actividad significativa cerca de tu zona",
            "📚 Aprovecha para aprender sobre primeros auxilios",
            "🗂️ Mantén documentos importantes en lugar seguro",
            "📱 Igual instala una app de alertas sísmicas como respaldo",
        ]
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def obtener_sismos(dias: int, magnitud_min: float, region_params: dict) -> pd.DataFrame:
    fecha_fin    = datetime.utcnow()
    fecha_inicio = fecha_fin - timedelta(days=dias)
    params = {
        "format":       "geojson",
        "starttime":    fecha_inicio.strftime("%Y-%m-%d"),
        "endtime":      fecha_fin.strftime("%Y-%m-%d"),
        "minmagnitude": magnitud_min,
        "orderby":      "time",
        "limit":        1000,
        **region_params,
    }
    try:
        resp = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params=params, timeout=15)
        resp.raise_for_status()
        features = resp.json()["features"]
    except Exception as e:
        st.error(f"Error al conectar con USGS: {e}")
        return pd.DataFrame()

    registros = []
    for f in features:
        p = f["properties"]
        c = f["geometry"]["coordinates"]
        registros.append({
            "lugar":       p.get("place", "Desconocido"),
            "magnitud":    float(p.get("mag") or 0),
            "profundidad": float(c[2]),
            "lon":         float(c[0]),
            "lat":         float(c[1]),
            "tiempo":      datetime.utcfromtimestamp(p["time"] / 1000),
            "tipo":        p.get("type", "earthquake"),
        })
    return pd.DataFrame(registros)


def color_magnitud(mag: float) -> str:
    if mag >= 7.0: return "#FF0000"
    if mag >= 6.0: return "#FF4B4B"
    if mag >= 5.0: return "#FF8C00"
    if mag >= 4.0: return "#FFD700"
    if mag >= 3.0: return "#ADFF2F"
    return "#00FF88"


def folium_color(mag: float) -> str:
    if mag >= 6.0: return "red"
    if mag >= 4.5: return "orange"
    if mag >= 3.0: return "beige"
    return "green"


def calcular_distancia_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def analizar_zona_riesgo(df: pd.DataFrame, lat: float, lon: float, radio_km: int) -> dict:
    df = df.copy()
    df["distancia_km"] = df.apply(lambda r: calcular_distancia_km(lat, lon, r["lat"], r["lon"]), axis=1)
    cercanos = df[df["distancia_km"] <= radio_km]
    if cercanos.empty:
        return {"total": 0, "mag_max": 0, "mag_prom": 0, "mas_cercano_km": None, "cercanos": cercanos, "nivel": "BAJO"}
    mag_max = cercanos["magnitud"].max()
    nivel = "CRÍTICO" if mag_max >= 7.0 else "ALTO" if mag_max >= 5.5 else "MEDIO" if mag_max >= 3.5 else "BAJO"
    return {
        "total":          len(cercanos),
        "mag_max":        round(mag_max, 1),
        "mag_prom":       round(cercanos["magnitud"].mean(), 1),
        "mas_cercano_km": round(cercanos["distancia_km"].min(), 1),
        "cercanos":       cercanos.sort_values("distancia_km"),
        "nivel":          nivel,
    }


def predecir_replicas(magnitud_principal: float, horas: list) -> list:
    K = 10 ** (magnitud_principal - 3.5)
    c, p = 0.1, 1.1
    return [round(K / (t + c) ** p, 2) for t in horas]


def es_riesgo_tsunami(mag: float, prof: float, lat: float, lon: float) -> bool:
    return mag >= 7.0 and prof <= 70


def comparar_semanas(dias_actual: int, magnitud_min: float, region_params: dict):
    df_actual  = obtener_sismos(dias_actual, magnitud_min, region_params)
    df_anterior = obtener_sismos(dias_actual * 2, magnitud_min, region_params)
    if df_actual.empty or df_anterior.empty:
        return None, None
    corte = datetime.utcnow() - timedelta(days=dias_actual)
    df_anterior = df_anterior[df_anterior["tiempo"] < corte]
    return len(df_actual), len(df_anterior)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
# ── Imagen de fondo ──────────────────────────────────────────────────────────
BG_EXTENSIONS = ["bg.jpg", "bg.jpeg", "bg.png", "bg.webp"]
BG_PATH = None
for ext in BG_EXTENSIONS:
    candidate = os.path.join(os.path.dirname(__file__), ext)
    if os.path.exists(candidate):
        BG_PATH = candidate
        break

if BG_PATH:
    with open(BG_PATH, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    ext_mime = "jpeg" if BG_PATH.endswith(".jpg") or BG_PATH.endswith(".jpeg") else BG_PATH.split(".")[-1]
    st.markdown(f"""
    <style>
    .stApp {{
        background-image: url("data:image/{ext_mime};base64,{encoded}") !important;
        background-size: cover !important;
        background-position: center center !important;
        background-attachment: fixed !important;
        background-repeat: no-repeat !important;
    }}
    .stApp::after {{
        content: '';
        position: fixed;
        inset: 0;
        background: rgba(8, 8, 15, 0.72);
        z-index: 0;
        pointer-events: none;
    }}
    </style>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="orb orb-1"></div>
<div class="orb orb-2"></div>
<div class="orb orb-3"></div>
<div class="orb orb-4"></div>

<div class="hero-header">
    <div class="hero-title">🌍 SismoAlert Pro</div>
    <div class="hero-subtitle">Monitoreo Sísmico Inteligente en Tiempo Real</div>
    <div class="wave-container">
        <svg viewBox="0 0 1200 80" preserveAspectRatio="none" class="seismic-wave">
            <polyline id="wave-line" points="" stroke="#FF4B4B" stroke-width="2.5"
                      fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.8"/>
        </svg>
    </div>
    <div style="color:rgba(255,255,255,0.3);font-size:0.75rem;margin-top:0.5rem;letter-spacing:2px;">
        🕐 Datos en tiempo real · USGS Earthquake Hazards Program
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    region_nombre = st.selectbox("Región", list(REGIONES.keys()))
    region_params = REGIONES[region_nombre]
    dias         = st.slider("Últimos días", 1, 30, 7)
    magnitud_min = st.slider("Magnitud mínima", 0.0, 7.0, 2.5, 0.5)
    radio_riesgo = st.slider("Radio de riesgo (km)", 100, 2000, 500, 100)

    st.markdown("---")
    st.markdown("### 📍 Mi ubicación")
    st.caption("Puedes elegir una ciudad o permitir que el navegador detecte tu ubicación actual.")

    # Geolocalización real desde el navegador del celular/PC.
    ubicacion = streamlit_geolocation()
    if ubicacion and ubicacion.get("latitude") is not None and ubicacion.get("longitude") is not None:
        lat_auto = float(ubicacion["latitude"])
        lon_auto = float(ubicacion["longitude"])
        st.success(f"📍 Ubicación detectada: {lat_auto:.5f}, {lon_auto:.5f}")
    else:
        lat_auto = lon_auto = None

    ciudad_sel = st.selectbox("Ciudad de referencia", list(CIUDADES_REF.keys()))

    if lat_auto is not None and ciudad_sel == "Personalizada":
        lat_usuario, lon_usuario = lat_auto, lon_auto
        st.caption("Usando la ubicación detectada por el dispositivo.")
    elif ciudad_sel == "Personalizada" or CIUDADES_REF[ciudad_sel] is None:
        lat_usuario = st.number_input("Latitud", value=4.7110, format="%.4f")
        lon_usuario = st.number_input("Longitud", value=-74.0721, format="%.4f")
    else:
        lat_usuario, lon_usuario = CIUDADES_REF[ciudad_sel]
        st.caption(f"📌 {lat_usuario:.4f}, {lon_usuario:.4f}")

    st.markdown("---")
    vista_mapa = st.selectbox("Vista del mapa", ["Puntos por magnitud", "Mapa de calor (heatmap)", "Ambos"])
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()

    st.markdown("---")
    st.caption("Datos: USGS · Actualización cada 5 min")
    st.caption("Proyecto de grado — Tecnólogo ADSO")


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════════════════════
with st.spinner("🌐 Conectando con servidores USGS..."):
    df = obtener_sismos(dias, magnitud_min, region_params)

if df.empty:
    st.warning("No se obtuvieron datos. Verifica tu conexión a internet.")
    st.stop()

# ── Ticker de sismos en vivo ─────────────────────────────────────────────────
def mag_clase(m):
    if m >= 5.5: return "ticker-mag-high"
    if m >= 4.0: return "ticker-mag-medium"
    return "ticker-mag-low"

ticker_items = ""
for _, r in df.head(20).iterrows():
    cls   = mag_clase(r["magnitud"])
    fecha = r["tiempo"].strftime("%d/%m %H:%M")
    ticker_items += (
        f'<span class="ticker-item">'
        f'<span class="{cls}">M{r["magnitud"]}</span> · '
        f'{r["lugar"]} · {fecha} UTC'
        f'</span> ·'
    )

st.markdown(f"""
<div class="ticker-wrapper">
    <div class="ticker-label">🔴 EN VIVO</div>
    <div class="ticker-track">
        <div class="ticker-content">{ticker_items}{ticker_items}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Alarma sonora y visual ───────────────────────────────────────────────────
def reproducir_alarma(nivel: str, magnitud: float = 0):
    """
    Inyecta una alarma sonora generada con Web Audio API según el nivel de alerta.
    nivel: 'CRITICO' | 'ALTO' | 'MEDIO'
    """
    if nivel == "CRITICO":
        # Sirena de emergencia: tono oscilante rojo
        script = f"""
        <script>
        (function() {{
            // Mostrar banner de alerta pulsante
            var banner = document.createElement('div');
            banner.id = 'sismo-banner';
            banner.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; z-index: 99999;
                background: linear-gradient(90deg, #ff0000, #cc0000, #ff0000);
                color: white; font-size: 1.2rem; font-weight: 900;
                padding: 14px; text-align: center; letter-spacing: 2px;
                animation: blink-banner 0.8s ease-in-out infinite;
                box-shadow: 0 4px 30px rgba(255,0,0,0.7);
            `;
            banner.innerHTML = '🚨 ALERTA SÍSMICA CRÍTICA — M{magnitud:.1f} DETECTADO — TOMA PRECAUCIONES INMEDIATAS 🚨';
            document.body.prepend(banner);

            // Agregar estilo de animación
            var style = document.createElement('style');
            style.textContent = '@keyframes blink-banner {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.6; }} }}';
            document.head.appendChild(style);

            // Cerrar banner al hacer click
            banner.addEventListener('click', function() {{ banner.remove(); }});

            // Alarma sonora — sirena oscilante
            try {{
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                function beep(freq, duration, delay) {{
                    setTimeout(function() {{
                        var osc = ctx.createOscillator();
                        var gain = ctx.createGain();
                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(freq, ctx.currentTime);
                        osc.frequency.linearRampToValueAtTime(freq * 1.5, ctx.currentTime + duration / 2);
                        osc.frequency.linearRampToValueAtTime(freq, ctx.currentTime + duration);
                        gain.gain.setValueAtTime(0.4, ctx.currentTime);
                        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
                        osc.start(ctx.currentTime);
                        osc.stop(ctx.currentTime + duration);
                    }}, delay);
                }}
                // 5 pulsos de sirena
                for (var i = 0; i < 5; i++) {{
                    beep(440, 0.4, i * 500);
                    beep(880, 0.4, i * 500 + 250);
                }}
            }} catch(e) {{ console.log('Audio no disponible:', e); }}
        }})();
        </script>
        """
    elif nivel == "ALTO":
        script = f"""
        <script>
        (function() {{
            var banner = document.createElement('div');
            banner.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; z-index: 99999;
                background: linear-gradient(90deg, #FF4B4B, #cc3300);
                color: white; font-size: 1rem; font-weight: 700;
                padding: 10px; text-align: center; letter-spacing: 1px;
                box-shadow: 0 4px 20px rgba(255,75,75,0.5);
            `;
            banner.innerHTML = '🔴 ALERTA ALTA — M{magnitud:.1f} — Monitorea la situación (click para cerrar)';
            banner.style.cursor = 'pointer';
            document.body.prepend(banner);
            banner.addEventListener('click', function() {{ banner.remove(); }});

            try {{
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                function beep(freq, duration, delay) {{
                    setTimeout(function() {{
                        var osc = ctx.createOscillator();
                        var gain = ctx.createGain();
                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.type = 'sine';
                        osc.frequency.value = freq;
                        gain.gain.setValueAtTime(0.3, ctx.currentTime);
                        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
                        osc.start(ctx.currentTime);
                        osc.stop(ctx.currentTime + duration);
                    }}, delay);
                }}
                beep(660, 0.3, 0);
                beep(880, 0.3, 350);
                beep(660, 0.3, 700);
            }} catch(e) {{ }}
        }})();
        </script>
        """
    elif nivel == "MEDIO":
        script = f"""
        <script>
        (function() {{
            try {{
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = 'sine';
                osc.frequency.value = 520;
                gain.gain.setValueAtTime(0.2, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.5);
            }} catch(e) {{ }}
        }})();
        </script>
        """
    else:
        return

    components.html(script, height=0)


# Alerta crítica si hay sismo >= 6.5 en los últimos datos
sismos_criticos = df[df["magnitud"] >= 6.5]
sismos_altos    = df[(df["magnitud"] >= 5.5) & (df["magnitud"] < 6.5)]
sismos_medios   = df[(df["magnitud"] >= 4.5) & (df["magnitud"] < 5.5)]

if not sismos_criticos.empty:
    ultimo_critico = sismos_criticos.iloc[0]
    st.markdown(f"""
    <div class="alert-critica">
        🚨 <strong>ALERTA SÍSMICA CRÍTICA:</strong> Se detectó un sismo de <strong>M{ultimo_critico['magnitud']}</strong>
        en <em>{ultimo_critico['lugar']}</em> el {ultimo_critico['tiempo'].strftime('%d/%m/%Y %H:%M')} UTC
    </div>
    """, unsafe_allow_html=True)
    reproducir_alarma("CRITICO", ultimo_critico['magnitud'])
    st.markdown("")

elif not sismos_altos.empty:
    ultimo_alto = sismos_altos.iloc[0]
    st.markdown(f"""
    <div class="alert-alto">
        🔴 <strong>ALERTA ALTA:</strong> Sismo de <strong>M{ultimo_alto['magnitud']}</strong>
        en <em>{ultimo_alto['lugar']}</em> el {ultimo_alto['tiempo'].strftime('%d/%m/%Y %H:%M')} UTC
    </div>
    """, unsafe_allow_html=True)
    reproducir_alarma("ALTO", ultimo_alto['magnitud'])
    st.markdown("")

elif not sismos_medios.empty:
    ultimo_medio = sismos_medios.iloc[0]
    st.markdown(f"""
    <div class="alert-medio">
        🟠 <strong>ACTIVIDAD MODERADA:</strong> Sismo de <strong>M{ultimo_medio['magnitud']}</strong>
        en <em>{ultimo_medio['lugar']}</em> el {ultimo_medio['tiempo'].strftime('%d/%m/%Y %H:%M')} UTC
    </div>
    """, unsafe_allow_html=True)
    reproducir_alarma("MEDIO", ultimo_medio['magnitud'])
    st.markdown("")


# ══════════════════════════════════════════════════════════════════════════════
# MÉTRICAS
# ══════════════════════════════════════════════════════════════════════════════
actual, anterior = comparar_semanas(dias, magnitud_min, region_params)
tendencia = ""
if actual is not None and anterior is not None and anterior > 0:
    pct = ((actual - anterior) / anterior) * 100
    tendencia = f"{'▲' if pct > 0 else '▼'} {abs(pct):.0f}% vs período anterior"

total_s   = len(df)
mag_max_v = float(df["magnitud"].max())
prof_v    = float(df["profundidad"].mean())
ultimo_v  = df["tiempo"].max().strftime("%d/%m")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    components.html(f"""
    <div class="glass-card" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
         border-radius:16px;padding:1.5rem;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
      <div id="cnt-total" style="font-size:2.2rem;font-weight:900;
           background:linear-gradient(135deg,#FF4B4B,#FF8C00);-webkit-background-clip:text;
           -webkit-text-fill-color:transparent;">0</div>
      <div style="color:rgba(255,255,255,0.4);font-size:0.75rem;text-transform:uppercase;letter-spacing:1.5px;">Total sismos</div>
    </div>
    <script>
    (function(){{
      let v=0, target={total_s};
      const el=document.getElementById('cnt-total');
      const step=Math.max(1,Math.ceil(target/40));
      const t=setInterval(()=>{{ v=Math.min(v+step,target); el.textContent=v; if(v>=target)clearInterval(t); }},30);
    }})();
    </script>
    """, height=110)

with col2:
    components.html(f"""
    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
         border-radius:16px;padding:1.5rem;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
      <div id="cnt-mag" style="font-size:2.2rem;font-weight:900;
           background:linear-gradient(135deg,#FF4B4B,#FF8C00);-webkit-background-clip:text;
           -webkit-text-fill-color:transparent;">M0.0</div>
      <div style="color:rgba(255,255,255,0.4);font-size:0.75rem;text-transform:uppercase;letter-spacing:1.5px;">Magnitud máxima</div>
    </div>
    <script>
    (function(){{
      let v=0, target={mag_max_v};
      const el=document.getElementById('cnt-mag');
      const steps=30;
      let i=0;
      const t=setInterval(()=>{{ i++; v=parseFloat((target*i/steps).toFixed(1));
        el.textContent='M'+v.toFixed(1); if(i>=steps)clearInterval(t); }},35);
    }})();
    </script>
    """, height=110)

with col3:
    components.html(f"""
    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
         border-radius:16px;padding:1.5rem;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
      <div id="cnt-prof" style="font-size:2.2rem;font-weight:900;
           background:linear-gradient(135deg,#FF4B4B,#FF8C00);-webkit-background-clip:text;
           -webkit-text-fill-color:transparent;">0 km</div>
      <div style="color:rgba(255,255,255,0.4);font-size:0.75rem;text-transform:uppercase;letter-spacing:1.5px;">Prof. promedio</div>
    </div>
    <script>
    (function(){{
      let v=0, target={prof_v:.0f};
      const el=document.getElementById('cnt-prof');
      const step=Math.max(1,Math.ceil(target/40));
      const t=setInterval(()=>{{ v=Math.min(v+step,target); el.textContent=v+' km'; if(v>=target)clearInterval(t); }},30);
    }})();
    </script>
    """, height=110)

with col4:
    st.markdown(f'<div class="glass-card" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:1.5rem;text-align:center;"><div class="metric-value" style="font-size:2.2rem;font-weight:900;background:linear-gradient(135deg,#FF4B4B,#FF8C00);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{ultimo_v}</div><div style="color:rgba(255,255,255,0.4);font-size:0.75rem;text-transform:uppercase;letter-spacing:1.5px;">Último registro</div></div>', unsafe_allow_html=True)

with col5:
    st.markdown(f'<div class="glass-card" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:1.5rem;text-align:center;"><div class="metric-value" style="font-size:1.4rem;font-weight:700;background:linear-gradient(135deg,#FF4B4B,#FF8C00);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{tendencia if tendencia else "Estable"}</div><div style="color:rgba(255,255,255,0.4);font-size:0.75rem;text-transform:uppercase;letter-spacing:1.5px;">Tendencia</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗺️ Mapa en vivo",
    "📊 Estadísticas",
    "📍 Mi zona de riesgo",
    "🔮 Predicción réplicas",
    "🌊 Riesgo Tsunami",
    "🔬 Análisis Predictivo",
])


# ┌──────────────────────────────────────────────────────────────┐
# │  TAB 1 — MAPA                                                │
# └──────────────────────────────────────────────────────────────┘
with tab1:
    lat_c, lon_c, zoom = REGION_CENTRO[region_nombre]
    centro = [lat_c, lon_c]
    m = folium.Map(location=centro, zoom_start=zoom, tiles="CartoDB dark_matter")

    if vista_mapa in ["Puntos por magnitud", "Ambos"]:
        cluster = MarkerCluster(disableClusteringAtZoom=6).add_to(m)
        for _, row in df.iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=max(4, row["magnitud"] * 3.5),
                color=color_magnitud(row["magnitud"]),
                fill=True, fill_opacity=0.75,
                popup=folium.Popup(
                    f"<div style='font-family:sans-serif;min-width:200px'>"
                    f"<b style='color:#FF4B4B'>{row['lugar']}</b><br>"
                    f"<b>Magnitud:</b> {row['magnitud']}<br>"
                    f"<b>Profundidad:</b> {row['profundidad']:.1f} km<br>"
                    f"<b>Fecha:</b> {row['tiempo'].strftime('%Y-%m-%d %H:%M')} UTC</div>",
                    max_width=260
                ),
            ).add_to(cluster)

    if vista_mapa in ["Mapa de calor (heatmap)", "Ambos"]:
        heat_data = [[row["lat"], row["lon"], row["magnitud"]] for _, row in df.iterrows()]
        HeatMap(heat_data, radius=15, blur=20, max_zoom=10,
                gradient={"0.2": "blue", "0.5": "orange", "0.8": "red", "1.0": "white"}).add_to(m)

    folium.Marker(
        location=[lat_usuario, lon_usuario],
        popup="📍 Tu ubicación",
        icon=folium.Icon(color="blue", icon="home", prefix="fa"),
    ).add_to(m)

    st_folium(m, width="100%", height=540)

    st.markdown("""
    🔴 `M ≥ 7.0` Muy alto &nbsp;|&nbsp;
    🔶 `M 5.0–6.9` Alto &nbsp;|&nbsp;
    🟡 `M 4.0–4.9` Moderado &nbsp;|&nbsp;
    🟢 `M 3.0–3.9` Leve &nbsp;|&nbsp;
    💚 `M < 3.0` Menor
    """)


# ┌──────────────────────────────────────────────────────────────┐
# │  TAB 2 — ESTADÍSTICAS                                        │
# └──────────────────────────────────────────────────────────────┘
with tab2:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(df, x="magnitud", nbins=25,
            title="Distribución de magnitudes",
            color_discrete_sequence=["#FF4B4B"], template="plotly_dark")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        df_d = df.copy()
        df_d["fecha"] = df_d["tiempo"].dt.date
        por_dia = df_d.groupby("fecha").size().reset_index(name="sismos")
        fig2 = px.area(por_dia, x="fecha", y="sismos",
            title="Actividad sísmica por día",
            template="plotly_dark", color_discrete_sequence=["#FF4B4B"])
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig3 = px.scatter(df, x="profundidad", y="magnitud",
            color="magnitud", size="magnitud", size_max=20,
            title="Profundidad vs Magnitud",
            template="plotly_dark", color_continuous_scale="Reds",
            hover_data=["lugar"])
        fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        conteo_tipo = df["tipo"].value_counts().reset_index()
        conteo_tipo.columns = ["tipo", "count"]
        fig4 = px.pie(conteo_tipo, values="count", names="tipo",
            title="Tipos de evento",
            template="plotly_dark",
            color_discrete_sequence=px.colors.sequential.Reds_r)
        fig4.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig4, use_container_width=True)

    if actual is not None and anterior is not None and anterior > 0:
        pct_local = ((actual - anterior) / anterior) * 100
        st.markdown("---")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Período actual",   actual, delta=f"{actual-anterior:+d} vs anterior")
        cc2.metric("Período anterior", anterior)
        cc3.metric("Tendencia", f"{pct_local:+.1f}%",
                   delta_color="inverse" if pct_local > 0 else "normal")

    st.markdown("#### 🔟 Sismos más recientes")
    st.dataframe(
        df[["tiempo","lugar","magnitud","profundidad"]].head(10).rename(columns={
            "tiempo":"Fecha UTC","lugar":"Lugar","magnitud":"Magnitud","profundidad":"Prof (km)"
        }),
        use_container_width=True, hide_index=True
    )


# ┌──────────────────────────────────────────────────────────────┐
# │  TAB 3 — ZONA DE RIESGO + PLAN DE ACCIÓN                    │
# └──────────────────────────────────────────────────────────────┘
with tab3:
    st.subheader(f"📍 Zona de riesgo — radio {radio_riesgo} km")
    analisis = analizar_zona_riesgo(df, lat_usuario, lon_usuario, radio_riesgo)
    nivel    = analisis["nivel"]
    plan     = PLAN_ACCION[nivel]

    st.markdown(f"""
    <div class="{plan['color']}">
        <h3>{plan['icono']} {plan['titulo']}</h3>
        {"<p>No se registraron sismos significativos en tu zona.</p>" if analisis['total'] == 0 else
         f"<p>Se encontraron <b>{analisis['total']}</b> sismos en {radio_riesgo} km · "
         f"Magnitud máx: <b>M{analisis['mag_max']}</b> · "
         f"Más cercano: <b>{analisis['mas_cercano_km']} km</b></p>"}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>**🆘 Plan de acción recomendado:**", unsafe_allow_html=True)
    for paso in plan["pasos"]:
        st.markdown(f'<div class="plan-card"><div class="plan-step">{paso}</div></div>', unsafe_allow_html=True)

    if analisis["total"] > 0:
        st.markdown("<br>#### Sismos más cercanos a ti", unsafe_allow_html=True)
        cerca = analisis["cercanos"][["distancia_km","lugar","magnitud","profundidad","tiempo"]].head(10)
        cerca = cerca.rename(columns={
            "distancia_km":"Distancia (km)","lugar":"Lugar",
            "magnitud":"Magnitud","profundidad":"Prof (km)","tiempo":"Fecha UTC"
        })
        st.dataframe(cerca, use_container_width=True, hide_index=True)

        mz = folium.Map(location=[lat_usuario, lon_usuario], zoom_start=5, tiles="CartoDB dark_matter")
        folium.Circle([lat_usuario, lon_usuario], radius=radio_riesgo*1000,
                      color="cyan", fill=True, fill_opacity=0.05).add_to(mz)
        folium.Marker([lat_usuario, lon_usuario],
                      icon=folium.Icon(color="blue", icon="home")).add_to(mz)
        for _, row in analisis["cercanos"].iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=max(4, row["magnitud"] * 3),
                color=color_magnitud(row["magnitud"]),
                fill=True, fill_opacity=0.8,
                popup=f"{row['lugar']} · M{row['magnitud']}",
            ).add_to(mz)
        st_folium(mz, width="100%", height=420)


# ┌──────────────────────────────────────────────────────────────┐
# │  TAB 4 — PREDICCIÓN RÉPLICAS                                 │
# └──────────────────────────────────────────────────────────────┘
with tab4:
    st.subheader("🔮 Predicción de réplicas — Ley de Omori")
    st.info("La **Ley de Omori** (Utsu, 1961) es la misma fórmula que usan los sismólogos profesionales para estimar réplicas después de un sismo principal.")

    cc1, cc2 = st.columns([2, 1])
    with cc1:
        mag_principal = st.slider("Magnitud del sismo principal", 4.0, 9.5, 6.5, 0.1)
    with cc2:
        horas_mostrar = st.selectbox("Ver primeras", [24, 48, 72, 168], index=2)
        horas_mostrar_label = {24:"24 horas", 48:"48 horas", 72:"72 horas", 168:"7 días"}[horas_mostrar]

    horas  = list(range(1, horas_mostrar + 1))
    reps   = predecir_replicas(mag_principal, horas)

    fig_o = go.Figure()
    fig_o.add_trace(go.Scatter(
        x=horas, y=reps, mode="lines",
        line=dict(color="#FF4B4B", width=2.5),
        fill="tozeroy", fillcolor="rgba(255,75,75,0.08)",
        name="Réplicas/hora",
    ))
    fig_o.update_layout(
        title=f"Réplicas esperadas tras sismo M{mag_principal} — primeras {horas_mostrar_label}",
        xaxis_title="Horas después del sismo",
        yaxis_title="Réplicas esperadas por hora",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_o, use_container_width=True)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Hora 1",   f"{reps[0]:.1f} réplicas")
    r2.metric("Hora 6",   f"{reps[5]:.1f} réplicas")
    r3.metric("Hora 24",  f"{reps[23]:.1f} réplicas" if len(reps) > 23 else "—")
    r4.metric("Hora 72",  f"{reps[71]:.1f} réplicas" if len(reps) > 71 else "—")

    st.caption("Solo para fines educativos. No reemplaza alertas oficiales de organismos sismológicos.")


# ┌──────────────────────────────────────────────────────────────┐
# │  TAB 5 — RIESGO DE TSUNAMI                                   │
# └──────────────────────────────────────────────────────────────┘
with tab5:
    st.subheader("🌊 Evaluación de riesgo de tsunami")
    st.markdown("""
    Un tsunami puede generarse cuando se cumplen **tres condiciones simultáneas**:
    - Magnitud **≥ 7.0**
    - Profundidad **≤ 70 km** (superficial)
    - Epicentro en zona **costera o submarina**
    """)

    potenciales = df[
        (df["magnitud"] >= 7.0) &
        (df["profundidad"] <= 70)
    ].copy()

    if potenciales.empty:
        st.markdown('<div class="alert-bajo"><h3>✅ Sin alertas de tsunami en el período seleccionado</h3><p>No se detectaron sismos con potencial tsunamigénico.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert-critica"><h3>🌊 {len(potenciales)} sismo(s) con potencial tsunamigénico detectados</h3></div>', unsafe_allow_html=True)
        st.markdown("")
        for _, row in potenciales.iterrows():
            st.markdown(f"""
            <div class="tsunami-badge">
                🌊 M{row['magnitud']} · {row['lugar']} · Prof: {row['profundidad']:.0f} km · {row['tiempo'].strftime('%d/%m %H:%M')} UTC
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### ¿Qué hacer ante alerta de tsunami?")
    pasos_tsunami = [
        "🏃 Evacúa inmediatamente hacia terrenos elevados (mínimo 30m sobre el nivel del mar)",
        "🚗 Si vas en vehículo, abandónalo si hay tráfico — continúa a pie",
        "📻 Escucha instrucciones de Defensa Civil o autoridades locales",
        "🚫 No vuelvas a la costa hasta que las autoridades lo declaren seguro",
        "⏱️ El mar puede retroceder antes del tsunami — es la señal de evacuación inmediata",
        "📱 Alerta a familiares y vecinos en zonas costeras",
    ]
    for paso in pasos_tsunami:
        st.markdown(f'<div class="plan-card"><div class="plan-step">{paso}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Fuente de criterios: NOAA Tsunami Warning Center · IOC-UNESCO")


# ┌──────────────────────────────────────────────────────────────┐
# │  TAB 6 — ANÁLISIS PREDICTIVO                                 │
# └──────────────────────────────────────────────────────────────┘
with tab6:
    st.subheader("🔬 Análisis Predictivo Sísmico")
    st.markdown("""
    > Herramientas estadísticas reales usadas por sismólogos para monitorear
    > el comportamiento de una región y detectar patrones inusuales.
    > **No predicen un sismo exacto**, pero identifican cuando una zona
    > muestra actividad fuera de lo normal.
    """)

    # Guardar registro automático cada vez que se carga esta tab
    guardar_registro(region_nombre, df, dias)

    # ── Score general ──────────────────────────────────────────
    score_data = calcular_score(df)
    score_val  = score_data["score"]

    st.markdown("### Score de actividad inusual")
    col_s1, col_s2 = st.columns([1, 2])

    with col_s1:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score_val,
            title={"text": score_data["nivel"], "font": {"size": 16, "color": score_data["color"]}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "white"},
                "bar":  {"color": score_data["color"]},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [0,  40], "color": "rgba(0,204,68,0.15)"},
                    {"range": [40, 70], "color": "rgba(255,215,0,0.15)"},
                    {"range": [70, 85], "color": "rgba(255,140,0,0.15)"},
                    {"range": [85,100], "color": "rgba(255,0,0,0.15)"},
                ],
                "threshold": {"line": {"color": "white", "width": 2}, "thickness": 0.75, "value": score_val},
            },
            number={"suffix": "/100", "font": {"color": score_data["color"], "size": 36}},
        ))
        fig_gauge.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", height=280,
            margin=dict(t=40, b=10, l=20, r=20),
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_s2:
        st.markdown(f"**{score_data['descripcion']}**")
        st.markdown("#### Composición del score")
        comp = score_data["componentes"]
        for nombre, valor in [
            ("Anomalía de frecuencia (0–50 pts)", comp["anomalia_frecuencia"]),
            ("Desviación del b-value (0–30 pts)", comp["b_value_anomalia"]),
            ("Tendencia creciente (0–20 pts)",    comp["tendencia"]),
        ]:
            pct = int((valor / {"anomalia_frecuencia": 50, "b_value_anomalia": 30, "tendencia": 20}[
                [k for k, v in {"anomalia_frecuencia": comp["anomalia_frecuencia"],
                                 "b_value_anomalia": comp["b_value_anomalia"],
                                 "tendencia": comp["tendencia"]}.items() if v == valor][0]
            ]) * 100)
            st.markdown(f"**{nombre}:** {valor} pts")
            st.progress(min(pct, 100) / 100)

    st.markdown("---")

    # ── B-value ───────────────────────────────────────────────
    st.markdown("### Valor-b de Gutenberg-Richter")
    st.caption("El valor-b describe la proporción entre sismos pequeños y grandes. Un b-value < 0.8 puede indicar acumulación de estrés tectónico.")

    bv_data = calcular_b_value(df)
    gr_data = curva_gutenberg_richter(df)

    bv1, bv2, bv3 = st.columns(3)
    bv1.metric("Valor-b",   f"{bv_data['b_value']}" if bv_data['b_value'] else "N/A",
               help="Normal: 0.8–1.2 | Bajo (<0.8): posible estrés | Alto (>1.2): zona volcánica")
    bv2.metric("Valor-a",   f"{bv_data['a_value']}" if bv_data['a_value'] else "N/A",
               help="Productividad sísmica de la región")
    bv3.metric("Sismos analizados", bv_data["n"])

    st.markdown(f"**Interpretación:** {bv_data['interpretacion']}")

    if not gr_data.empty:
        fig_gr = go.Figure()
        fig_gr.add_trace(go.Scatter(
            x=gr_data["magnitud"], y=np.log10(gr_data["observado"] + 0.1),
            mode="markers", name="Observado",
            marker=dict(color="#FF4B4B", size=8),
        ))
        fig_gr.add_trace(go.Scatter(
            x=gr_data["magnitud"], y=np.log10(gr_data["teorico"] + 0.1),
            mode="lines", name="Teórico (Gutenberg-Richter)",
            line=dict(color="#FFD700", width=2, dash="dash"),
        ))
        fig_gr.update_layout(
            title="Relación Frecuencia-Magnitud (Gutenberg-Richter)",
            xaxis_title="Magnitud", yaxis_title="log₁₀(N acumulado)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_gr, use_container_width=True)

    st.markdown("---")

    # ── Detección de anomalías ────────────────────────────────
    st.markdown("### Detección de anomalías — Z-score")
    st.caption("Compara la actividad reciente vs el promedio histórico del período seleccionado.")

    anom = detectar_anomalias(df)

    if anom["z_score"] is not None:
        col_a1, col_a2, col_a3 = st.columns(3)
        col_a1.metric("Z-score", anom["z_score"],
                      help="0–1: normal | 1–2: levemente elevado | 2–3: inusual | >3: muy inusual")
        col_a2.metric("Promedio histórico", f"{anom['media_baseline']} sismos/día")
        col_a3.metric("Actividad reciente", f"{anom['prom_reciente']} sismos/día")
        st.markdown(f"**Nivel:** `{anom['nivel']}` — {anom['descripcion']}")

        conteo = anom["conteo_diario"]
        fig_anom = go.Figure()
        n_base = max(1, len(conteo) - 7)
        fig_anom.add_trace(go.Bar(
            x=conteo["fecha"].astype(str).iloc[:n_base],
            y=conteo["count"].iloc[:n_base],
            name="Período base", marker_color="rgba(100,100,255,0.5)",
        ))
        fig_anom.add_trace(go.Bar(
            x=conteo["fecha"].astype(str).iloc[n_base:],
            y=conteo["count"].iloc[n_base:],
            name="Período reciente", marker_color="#FF4B4B",
        ))
        fig_anom.add_hline(
            y=anom["media_baseline"], line_dash="dash", line_color="#FFD700",
            annotation_text=f"Promedio base: {anom['media_baseline']}",
        )
        fig_anom.update_layout(
            title="Sismos por día: base vs período reciente",
            xaxis_title="Fecha", yaxis_title="Número de sismos",
            barmode="overlay", template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_anom, use_container_width=True)
    else:
        st.info(anom["descripcion"])

    st.markdown("---")

    # ── Tendencia ─────────────────────────────────────────────
    st.markdown("### Tendencia de actividad")
    tend = calcular_tendencia(df)

    if tend["pendiente"] is not None:
        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Pendiente diaria", f"{tend['pendiente']:+.2f} sismos/día")
        col_t2.metric("Ajuste R²", f"{tend['r2']:.3f}",
                      help="0 = sin correlación | 1 = tendencia perfecta")
        st.markdown(f"**{tend['tendencia']}**")

        conteo_t = tend["conteo"]
        fig_tend = go.Figure()
        fig_tend.add_trace(go.Scatter(
            x=conteo_t["fecha"].astype(str), y=conteo_t["count"],
            mode="lines+markers", name="Sismos/día",
            line=dict(color="#FF4B4B", width=2),
            marker=dict(size=6),
        ))
        fig_tend.add_trace(go.Scatter(
            x=conteo_t["fecha"].astype(str), y=tend["y_regresion"],
            mode="lines", name="Tendencia (regresión lineal)",
            line=dict(color="#FFD700", width=2, dash="dot"),
        ))
        fig_tend.update_layout(
            title="Tendencia de actividad sísmica",
            xaxis_title="Fecha", yaxis_title="Sismos por día",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_tend, use_container_width=True)
    else:
        st.info(tend["tendencia"])

    st.markdown("---")

    # ── Historial de datos recopilados ────────────────────────
    st.markdown("### 📂 Datos históricos recopilados por tu app")
    st.caption("Cada vez que abres esta pestaña, tu app guarda un registro. Con el tiempo construyes tu propio dataset sísmico.")

    historial = cargar_historial()
    if historial.empty:
        st.info("Aún no hay datos guardados. ¡Acabas de guardar el primero!")
    else:
        st.success(f"✅ {len(historial)} registros recopilados desde que instalaste SismoAlert Pro")
        st.dataframe(
            historial.sort_values("timestamp", ascending=False).rename(columns={
                "timestamp":       "Fecha UTC",
                "region":          "Región",
                "dias_analizados": "Días",
                "total_sismos":    "Total sismos",
                "mag_max":         "Mag. máx",
                "mag_promedio":    "Mag. prom",
                "b_value":         "Valor-b",
                "score_anomalia":  "Score",
                "tendencia_diaria":"Tendencia/día",
            }),
            use_container_width=True, hide_index=True,
        )
        csv = historial.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar dataset completo (CSV)",
            data=csv, file_name="sismoalert_historico.csv", mime="text/csv",
        )

    st.caption("**Nota científica:** Estas herramientas son usadas por el USGS, IGP (Perú) y SGC (Colombia). No predicen sismos exactos — detectan anomalías estadísticas que los sismólogos usan como señales de monitoreo.")


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:rgba(255,255,255,0.2); font-size:0.75rem; padding:1rem'>
    SismoAlert Pro · Datos en tiempo real: USGS Earthquake Hazards Program · Actualización cada 5 minutos<br>
    Proyecto de Grado — Tecnólogo en Análisis y Desarrollo de Software
</div>
""", unsafe_allow_html=True)
