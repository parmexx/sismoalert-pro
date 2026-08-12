"""
Módulo de análisis sísmico predictivo.
Implementa herramientas reales usadas por sismólogos:
  - Ley de Gutenberg-Richter (valor-b)
  - Detección de anomalías por Z-score
  - Regresión lineal de tendencia
  - Score de actividad inusual
  - Logger de datos históricos propios
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "datos_historicos.csv")

COLUMNAS_LOG = [
    "timestamp", "region", "dias_analizados", "total_sismos",
    "mag_max", "mag_promedio", "b_value", "score_anomalia",
    "tendencia_diaria",
]


# ── Gutenberg-Richter b-value ─────────────────────────────────────────────

def calcular_b_value(df: pd.DataFrame, mc: float | None = None) -> dict:
    """
    Estimador de máxima verosimilitud de Aki (1965).

    b = log10(e) / (M_mean - Mc)

    Mc: magnitud de completitud (mínima magnitud confiable del catálogo).
    Un b-value normal está entre 0.8 y 1.2.
    Valores < 0.8 indican posible acumulación de estrés tectónico.
    """
    if df.empty or len(df) < 5:
        return {"b_value": None, "a_value": None, "mc": None, "n": 0, "interpretacion": "Datos insuficientes"}

    mc = mc if mc is not None else df["magnitud"].min()
    df_filtrado = df[df["magnitud"] >= mc]

    if len(df_filtrado) < 5:
        return {"b_value": None, "a_value": None, "mc": mc, "n": 0, "interpretacion": "Datos insuficientes"}

    M_mean = df_filtrado["magnitud"].mean()
    if M_mean <= mc:
        return {"b_value": None, "a_value": None, "mc": mc, "n": len(df_filtrado), "interpretacion": "Error en datos"}

    b = np.log10(np.e) / (M_mean - mc)
    a = np.log10(len(df_filtrado)) + b * mc

    if b < 0.6:
        interpretacion = "⚠️ Valor muy bajo — posible acumulación de estrés tectónico"
    elif b < 0.8:
        interpretacion = "🔶 Valor bajo — actividad tectónica elevada para esta zona"
    elif b <= 1.2:
        interpretacion = "✅ Valor normal — actividad sísmica típica"
    elif b <= 1.5:
        interpretacion = "🔵 Valor alto — zona con muchos sismos pequeños (zona volcánica o de baja tensión)"
    else:
        interpretacion = "🔵 Valor muy alto — zona volcánica o enjambre sísmico"

    return {
        "b_value":       round(b, 3),
        "a_value":       round(a, 3),
        "mc":            mc,
        "n":             len(df_filtrado),
        "interpretacion": interpretacion,
    }


def curva_gutenberg_richter(df: pd.DataFrame, mc: float | None = None) -> pd.DataFrame:
    """Genera los puntos observados y la línea teórica de Gutenberg-Richter."""
    if df.empty:
        return pd.DataFrame()

    mc = mc if mc is not None else df["magnitud"].min()
    bv = calcular_b_value(df, mc)
    if bv["b_value"] is None:
        return pd.DataFrame()

    magnitudes = np.arange(mc, df["magnitud"].max() + 0.5, 0.5)
    observado  = [len(df[df["magnitud"] >= m]) for m in magnitudes]
    teorico    = [10 ** (bv["a_value"] - bv["b_value"] * m) for m in magnitudes]

    return pd.DataFrame({
        "magnitud":  magnitudes,
        "observado": observado,
        "teorico":   teorico,
    })


# ── Detección de anomalías ────────────────────────────────────────────────

def detectar_anomalias(df: pd.DataFrame, ventana_baseline_dias: int = 21, ventana_actual_dias: int = 7) -> dict:
    """
    Compara la actividad reciente vs la línea base histórica usando Z-score.

    Z = (actual - media_historica) / desviacion_historica

    Z > 2  → actividad inusual (>2 desviaciones estándar)
    Z > 3  → actividad muy inusual
    """
    if df.empty or len(df) < 10:
        return {"z_score": None, "nivel": "Sin datos", "descripcion": "Datos insuficientes para análisis"}

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["tiempo"]).dt.date
    conteo_diario = df.groupby("fecha").size().reset_index(name="count")
    conteo_diario = conteo_diario.sort_values("fecha")

    if len(conteo_diario) < 5:
        return {"z_score": None, "nivel": "Sin datos", "descripcion": "Se necesitan al menos 5 días de datos"}

    # Baseline: todos los días excepto los más recientes
    n_recientes   = min(ventana_actual_dias, len(conteo_diario) // 3)
    baseline      = conteo_diario.iloc[:-n_recientes]["count"]
    reciente      = conteo_diario.iloc[-n_recientes:]["count"]

    media   = baseline.mean()
    std     = baseline.std()
    prom_reciente = reciente.mean()

    if std == 0 or np.isnan(std):
        z = 0.0
    else:
        z = (prom_reciente - media) / std

    if z > 3:
        nivel       = "MUY INUSUAL"
        descripcion = f"Actividad {prom_reciente:.1f} sismos/día vs promedio {media:.1f} — {z:.1f} desviaciones estándar sobre lo normal"
    elif z > 2:
        nivel       = "INUSUAL"
        descripcion = f"Actividad {prom_reciente:.1f} sismos/día vs promedio {media:.1f} — moderadamente elevada"
    elif z > 1:
        nivel       = "LEVEMENTE ELEVADA"
        descripcion = f"Actividad {prom_reciente:.1f} sismos/día vs promedio {media:.1f} — dentro del rango normal alto"
    elif z < -1:
        nivel       = "BAJA"
        descripcion = f"Actividad {prom_reciente:.1f} sismos/día vs promedio {media:.1f} — menor a lo esperado"
    else:
        nivel       = "NORMAL"
        descripcion = f"Actividad {prom_reciente:.1f} sismos/día vs promedio {media:.1f} — dentro del rango esperado"

    return {
        "z_score":       round(z, 2),
        "nivel":         nivel,
        "descripcion":   descripcion,
        "media_baseline": round(media, 2),
        "std_baseline":  round(std, 2),
        "prom_reciente": round(prom_reciente, 2),
        "conteo_diario": conteo_diario,
    }


# ── Tendencia de actividad ────────────────────────────────────────────────

def calcular_tendencia(df: pd.DataFrame) -> dict:
    """
    Regresión lineal sobre el conteo diario de sismos.
    Pendiente positiva = actividad en aumento.
    Pendiente negativa = actividad disminuyendo.
    """
    if df.empty:
        return {"pendiente": None, "r2": None, "tendencia": "Sin datos"}

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["tiempo"]).dt.date
    conteo = df.groupby("fecha").size().reset_index(name="count")

    if len(conteo) < 4:
        return {"pendiente": None, "r2": None, "tendencia": "Pocos datos"}

    x = np.arange(len(conteo))
    y = conteo["count"].values

    coefs  = np.polyfit(x, y, 1)
    y_pred = np.polyval(coefs, x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    pendiente = coefs[0]

    if pendiente > 1.5:
        tendencia = "📈 Aumento significativo de actividad"
    elif pendiente > 0.3:
        tendencia = "📈 Leve aumento de actividad"
    elif pendiente < -1.5:
        tendencia = "📉 Disminución significativa de actividad"
    elif pendiente < -0.3:
        tendencia = "📉 Leve disminución de actividad"
    else:
        tendencia = "➡️ Actividad estable"

    return {
        "pendiente":     round(pendiente, 3),
        "r2":            round(r2, 3),
        "tendencia":     tendencia,
        "conteo":        conteo,
        "y_regresion":   y_pred.tolist(),
    }


# ── Score de actividad inusual (0–100) ───────────────────────────────────

def calcular_score(df: pd.DataFrame, mc: float | None = None) -> dict:
    """
    Score compuesto 0–100 que combina:
      - Anomalía de frecuencia (Z-score)
      - Desviación del b-value respecto a 1.0
      - Tendencia reciente

    > 70 → zona de atención
    > 85 → zona de alerta
    """
    anomalia  = detectar_anomalias(df)
    bv        = calcular_b_value(df, mc)
    tendencia = calcular_tendencia(df)

    componentes = {}

    # Componente 1: anomalía de frecuencia (0-50 pts)
    z = anomalia.get("z_score") or 0
    comp_anomalia = min(50, max(0, z * 15))
    componentes["anomalia_frecuencia"] = round(comp_anomalia, 1)

    # Componente 2: desviación del b-value (0-30 pts)
    b = bv.get("b_value")
    if b is not None:
        desv_b = max(0, 1.0 - b)          # b < 1.0 es señal de alerta
        comp_b = min(30, desv_b * 40)
    else:
        comp_b = 0
    componentes["b_value_anomalia"] = round(comp_b, 1)

    # Componente 3: tendencia creciente (0-20 pts)
    pend = tendencia.get("pendiente") or 0
    comp_tend = min(20, max(0, pend * 5))
    componentes["tendencia"] = round(comp_tend, 1)

    score = comp_anomalia + comp_b + comp_tend

    if score >= 85:
        nivel = "🚨 ALERTA"
        color = "#FF0000"
        descripcion = "Actividad sísmica altamente inusual — monitoreo intensivo recomendado"
    elif score >= 70:
        nivel = "⚠️ ATENCIÓN"
        color = "#FF8C00"
        descripcion = "Actividad por encima de lo normal — seguimiento recomendado"
    elif score >= 40:
        nivel = "🔶 MODERADO"
        color = "#FFD700"
        descripcion = "Actividad ligeramente elevada — dentro de rangos observables"
    else:
        nivel = "✅ NORMAL"
        color = "#00CC44"
        descripcion = "Sin señales de actividad inusual en esta región"

    return {
        "score":        round(score, 1),
        "nivel":        nivel,
        "color":        color,
        "descripcion":  descripcion,
        "componentes":  componentes,
    }


# ── Logger de datos históricos ────────────────────────────────────────────

def guardar_registro(region: str, df: pd.DataFrame, dias: int) -> None:
    """Guarda un snapshot del análisis actual en el CSV histórico local."""
    if df.empty:
        return

    bv    = calcular_b_value(df)
    score = calcular_score(df)
    tend  = calcular_tendencia(df)

    registro = {
        "timestamp":        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "region":           region,
        "dias_analizados":  dias,
        "total_sismos":     len(df),
        "mag_max":          df["magnitud"].max(),
        "mag_promedio":     round(df["magnitud"].mean(), 3),
        "b_value":          bv.get("b_value"),
        "score_anomalia":   score["score"],
        "tendencia_diaria": tend.get("pendiente"),
    }

    fila = pd.DataFrame([registro])

    if os.path.exists(LOG_FILE):
        fila.to_csv(LOG_FILE, mode="a", header=False, index=False)
    else:
        fila.to_csv(LOG_FILE, mode="w", header=True, index=False)


def cargar_historial() -> pd.DataFrame:
    """Carga el historial de registros guardados."""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=COLUMNAS_LOG)
    try:
        return pd.read_csv(LOG_FILE, parse_dates=["timestamp"])
    except Exception:
        return pd.DataFrame(columns=COLUMNAS_LOG)
