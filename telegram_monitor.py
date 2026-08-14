"""
SismoAlert Pro — Monitor sísmico + Bot público de Telegram.

Funciones:
  1. Cualquier persona puede escribir /start al bot y suscribirse.
  2. Consulta USGS cada 5 minutos y envía alertas a TODOS los suscritos.
  3. Los suscriptores se guardan en telegram_subscribers.json (GitHub Actions).
  4. Comandos disponibles: /start, /stop, /status, /help
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# ── Configuración ─────────────────────────────────────────────────────────────
TOKEN      = os.environ["TELEGRAM_BOT_TOKEN"]
USGS_URL   = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EMSC_URL   = "https://www.seismicportal.eu/fdsnws/event/1/query"
SGC_URL    = "https://sgc.gov.co/sgc/sismos/fdsnws/event/1/query"
BOT_URL    = f"https://api.telegram.org/bot{TOKEN}"
COLOMBIA_TZ = ZoneInfo("America/Bogota")

STATE_FILE       = Path(__file__).with_name("telegram_alert_state.json")
SUBSCRIBERS_FILE = Path(__file__).with_name("telegram_subscribers.json")


# ── Manejo de suscriptores ────────────────────────────────────────────────────

def load_subscribers() -> set:
    """Carga la lista de chat_ids suscritos."""
    if not SUBSCRIBERS_FILE.exists():
        return set()
    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        return set(str(x) for x in data.get("subscribers", []))
    except Exception:
        return set()


def save_subscribers(subs: set) -> None:
    """Guarda la lista de chat_ids suscritos."""
    SUBSCRIBERS_FILE.write_text(
        json.dumps({"subscribers": list(subs)}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ── Manejo de estado de alertas ───────────────────────────────────────────────

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"sent": [], "last_update_id": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": [], "last_update_id": 0}


def save_state(state: dict) -> None:
    state["sent"] = state.get("sent", [])[-500:]
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ── Telegram helpers ──────────────────────────────────────────────────────────

def send_message(chat_id: str, text: str) -> bool:
    try:
        r = requests.post(
            f"{BOT_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


def get_updates(offset: int = 0) -> list:
    try:
        r = requests.get(
            f"{BOT_URL}/getUpdates",
            params={"offset": offset, "timeout": 5, "limit": 100},
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception:
        pass
    return []


# ── Procesar comandos del bot ─────────────────────────────────────────────────

def process_updates(state: dict, subscribers: set) -> tuple[dict, set]:
    """Procesa mensajes nuevos y maneja /start y /stop."""
    last_id = state.get("last_update_id", 0)
    updates = get_updates(offset=last_id + 1)

    for update in updates:
        last_id = max(last_id, update.get("update_id", 0))
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text    = message.get("text", "").strip().lower()
        nombre  = message.get("chat", {}).get("first_name", "amigo")

        if not chat_id:
            continue

        if text.startswith("/start"):
            if chat_id not in subscribers:
                subscribers.add(chat_id)
                save_subscribers(subscribers)
                send_message(chat_id, (
                    f"🌍 <b>¡Hola {nombre}! Bienvenido a SismoAlert Pro</b>\n\n"
                    f"✅ Te has suscrito correctamente.\n\n"
                    f"A partir de ahora recibirás alertas automáticas cuando se detecte "
                    f"actividad sísmica en cualquier parte del mundo.\n\n"
                    f"📋 <b>Comandos disponibles:</b>\n"
                    f"/start — Suscribirte a las alertas\n"
                    f"/stop — Cancelar suscripción\n"
                    f"/status — Ver estado del monitor\n"
                    f"/help — Ver ayuda\n\n"
                    f"🌐 App web: https://sismoalert-pro-since-2026.streamlit.app"
                ))
                print(f"✅ Nuevo suscriptor: {chat_id} ({nombre})")
            else:
                send_message(chat_id, (
                    f"✅ {nombre}, ya estás suscrito a SismoAlert Pro.\n"
                    f"Recibirás alertas automáticamente cuando haya actividad sísmica.\n\n"
                    f"Usa /stop si deseas cancelar la suscripción."
                ))

        elif text.startswith("/stop"):
            if chat_id in subscribers:
                subscribers.discard(chat_id)
                save_subscribers(subscribers)
                send_message(chat_id, (
                    f"😔 {nombre}, has cancelado tu suscripción a SismoAlert Pro.\n\n"
                    f"Ya no recibirás alertas sísmicas.\n"
                    f"Puedes volver a suscribirte cuando quieras con /start."
                ))
                print(f"❌ Suscriptor eliminado: {chat_id} ({nombre})")
            else:
                send_message(chat_id, "No estás suscrito. Usa /start para suscribirte.")

        elif text.startswith("/status"):
            n = len(subscribers)
            send_message(chat_id, (
                f"📊 <b>Estado de SismoAlert Pro</b>\n\n"
                f"👥 Suscriptores activos: <b>{n}</b>\n"
                f"🕐 Hora UTC: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}\n"
                f"🇨🇴 Hora Colombia: {datetime.now(COLOMBIA_TZ).strftime('%d/%m/%Y %H:%M')}\n"
                f"📡 Monitor: Activo (cada 5 minutos)\n"
                f"🌐 Fuente: USGS Earthquake Hazards Program"
            ))

        elif text.startswith("/help"):
            send_message(chat_id, (
                f"🌍 <b>SismoAlert Pro — Ayuda</b>\n\n"
                f"Este bot envía alertas automáticas de actividad sísmica "
                f"detectada por el USGS en tiempo real.\n\n"
                f"📋 <b>Comandos:</b>\n"
                f"/start — Suscribirte a las alertas\n"
                f"/stop — Cancelar suscripción\n"
                f"/status — Ver estado del monitor\n"
                f"/help — Ver esta ayuda\n\n"
                f"🌐 App web completa:\n"
                f"https://sismoalert-pro-since-2026.streamlit.app\n\n"
                f"⚠️ Las alertas son informativas. No reemplazan "
                f"los sistemas oficiales de emergencia."
            ))

    state["last_update_id"] = last_id
    return state, subscribers


# ── Consultar USGS y enviar alertas ──────────────────────────────────────────

EMSC_URL = "https://www.seismicportal.eu/fdsnws/event/1/query"

def obtener_sismos_usgs(start: datetime, now: datetime) -> list:
    """Consulta USGS y retorna lista de eventos normalizados."""
    params = {
        "format":       "geojson",
        "starttime":    start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime":      now.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby":      "time",
        "minmagnitude": 0.0,
        "limit":        20000,
    }
    try:
        resp = requests.get(USGS_URL, params=params, timeout=30)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        print(f"USGS: {len(features)} eventos")
        return [
            {
                "id":    f"usgs_{f.get('id','')}",
                "mag":   f.get("properties", {}).get("mag"),
                "place": f.get("properties", {}).get("place") or "Lugar no informado",
                "time":  f.get("properties", {}).get("time"),
                "depth": (f.get("geometry", {}).get("coordinates") or [None, None, None])[2],
                "fuente": "USGS"
            }
            for f in features if f.get("id")
        ]
    except Exception as e:
        print(f"Error USGS: {e}")
        return []


def obtener_sismos_emsc(start: datetime, now: datetime) -> list:
    """Consulta EMSC (cobertura mundial) y retorna lista normalizada."""
    params = {
        "format":       "json",
        "starttime":    start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime":      now.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby":      "time",
        "minmag":       0.0,
        "limit":        1000,
    }
    try:
        resp = requests.get(EMSC_URL, params=params, timeout=30)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        print(f"EMSC: {len(features)} eventos")
        eventos = []
        for f in features:
            props = f.get("properties", {})
            geo   = f.get("geometry", {}).get("coordinates") or [None, None, None]
            eid   = str(f.get("id") or props.get("unid") or "")
            if not eid:
                continue
            ts = props.get("time")
            if isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    ts_ms = int(dt.timestamp() * 1000)
                except Exception:
                    ts_ms = None
            else:
                ts_ms = ts
            eventos.append({
                "id":    f"emsc_{eid}",
                "mag":   props.get("mag"),
                "place": props.get("flynn_region") or props.get("place") or "Lugar no informado",
                "time":  ts_ms,
                "depth": geo[2],
                "fuente": "EMSC"
            })
        return eventos
    except Exception as e:
        print(f"Error EMSC: {e}")
        return []


def obtener_sismos_sgc(start: datetime, now: datetime) -> list:
    """Consulta SGC Colombia y retorna lista normalizada."""
    params = {
        "format":    "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime":   now.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby":   "time",
        "limit":     1000,
    }
    try:
        resp = requests.get(SGC_URL, params=params, timeout=30)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        print(f"SGC Colombia: {len(features)} eventos")
        eventos = []
        for f in features:
            props = f.get("properties", {})
            geo   = f.get("geometry", {}).get("coordinates") or [None, None, None]
            eid   = str(f.get("id") or "")
            if not eid:
                continue
            eventos.append({
                "id":     f"sgc_{eid}",
                "mag":    props.get("mag"),
                "place":  props.get("place") or props.get("description") or "Colombia",
                "time":   props.get("time"),
                "depth":  geo[2],
                "fuente": "SGC Colombia"
            })
        return eventos
    except Exception as e:
        print(f"Error SGC: {e}")
        return []


def check_and_alert(state: dict, subscribers: set) -> dict:
    """Consulta USGS + EMSC y envía alertas a todos los suscriptores."""
    if not subscribers:
        print("Sin suscriptores aún.")
        return state

    now   = datetime.now(timezone.utc)
    start = now - timedelta(minutes=30)

    # Combinar eventos de las 3 fuentes
    eventos_usgs = obtener_sismos_usgs(start, now)
    eventos_emsc = obtener_sismos_emsc(start, now)
    eventos_sgc  = obtener_sismos_sgc(start, now)
    todos        = eventos_usgs + eventos_emsc + eventos_sgc
    print(f"Total eventos combinados: {len(todos)}")

    sent    = set(state.get("sent", []))
    nuevos  = 0

    for feature in todos:
        eid   = str(feature.get("id") or "")
        if not eid or eid in sent:
            continue

        mag    = feature.get("mag")
        place  = feature.get("place") or "Lugar no informado"
        ts     = feature.get("time")
        depth  = feature.get("depth")
        fuente = feature.get("fuente", "USGS")

        mag_text   = f"M{float(mag):.1f}" if mag is not None else "N/D"
        depth_text = f"{float(depth):.1f} km" if depth is not None else "N/D"

        if ts:
            utc_t = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            col_t = utc_t.astimezone(COLOMBIA_TZ)
            hora_utc = utc_t.strftime("%d/%m/%Y %H:%M UTC")
            hora_col = col_t.strftime("%d/%m/%Y %I:%M %p")
        else:
            hora_utc = hora_col = "No disponible"

        # Emoji según magnitud
        try:
            m = float(mag) if mag else 0
        except Exception:
            m = 0

        if m >= 7.0:
            emoji = "🚨🚨🚨"
            nivel = "CRÍTICO"
        elif m >= 6.0:
            emoji = "🔴🔴"
            nivel = "ALTO"
        elif m >= 5.0:
            emoji = "🟠"
            nivel = "MODERADO"
        elif m >= 4.0:
            emoji = "🟡"
            nivel = "LEVE"
        else:
            emoji = "🟢"
            nivel = "MENOR"

        mensaje = (
            f"{emoji} <b>SISMO {nivel} — {mag_text}</b>\n\n"
            f"📍 <b>Lugar:</b> {place}\n"
            f"⬇️ <b>Profundidad:</b> {depth_text}\n"
            f"🌐 <b>UTC:</b> {hora_utc}\n"
            f"🇨🇴 <b>Colombia:</b> {hora_col}\n\n"
            f"🌐 Ver en app: https://sismoalert-pro-since-2026.streamlit.app\n"
            f"📡 Fuente: {fuente}"
        )

        # Enviar a TODOS los suscriptores
        enviados = 0
        fallidos = []
        for cid in list(subscribers):
            ok = send_message(cid, mensaje)
            if ok:
                enviados += 1
            else:
                fallidos.append(cid)

        # Eliminar suscriptores que bloquearon el bot
        for cid in fallidos:
            subscribers.discard(cid)
            print(f"⚠️ Suscriptor eliminado (bloqueó el bot): {cid}")

        if enviados > 0:
            save_subscribers(subscribers)

        sent.add(eid)
        nuevos += 1
        print(f"✅ Alerta enviada a {enviados} personas: {mag_text} — {place}")

    state["sent"] = list(sent)
    print(f"Alertas nuevas enviadas: {nuevos} | Suscriptores: {len(subscribers)}")
    return state


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    state       = load_state()
    subscribers = load_subscribers()

    print(f"Suscriptores activos: {len(subscribers)}")

    # 1. Procesar comandos nuevos (/start, /stop, etc.)
    state, subscribers = process_updates(state, subscribers)

    # 2. Consultar USGS y enviar alertas
    state = check_and_alert(state, subscribers)

    # 3. Guardar estado
    save_state(state)


if __name__ == "__main__":
    main()
