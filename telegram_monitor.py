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

def load_subscribers(state: dict) -> set:
    """Carga suscriptores desde el estado principal, preservando los existentes."""
    subscribers = set(str(x) for x in state.get("subscribers", []))

    # Compatibilidad: si existe el archivo antiguo, lo incorporamos solo como respaldo.
    if SUBSCRIBERS_FILE.exists():
        try:
            data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            subscribers.update(str(x) for x in data.get("subscribers", []))
        except Exception:
            pass

    # Conserva el chat principal configurado en GitHub Actions.
    legacy_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if legacy_chat_id:
        subscribers.add(str(legacy_chat_id))

    return subscribers


def save_subscribers(subs: set) -> None:
    """Mantiene una copia compatible del archivo antiguo."""
    try:
        SUBSCRIBERS_FILE.write_text(
            json.dumps({"subscribers": sorted(subs)}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"⚠️ No se pudo actualizar archivo legado de suscriptores: {e}")


# ── Manejo de estado de alertas ───────────────────────────────────────────────

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"sent": [], "subscribers": [], "telegram_update_offset": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": [], "subscribers": [], "telegram_update_offset": 0}


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
    """Procesa /start, /stop, /status y /help usando un único estado persistente."""
    offset = int(state.get("telegram_update_offset", 0) or 0)
    updates = get_updates(offset=offset)

    for update in updates:
        update_id = update.get("update_id")
        if update_id is not None:
            offset = max(offset, int(update_id) + 1)

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = (message.get("text") or "").strip()
        nombre = chat.get("first_name", "amigo")

        if not chat_id:
            continue

        command = text.split()[0].split("@")[0].lower() if text else ""

        if command == "/start":
            is_new = chat_id not in subscribers
            subscribers.add(chat_id)
            if is_new:
                send_message(chat_id, (
                    f"🌍 <b>¡Hola {nombre}! Bienvenido a SismoAlert Pro</b>\n\n"
                    "✅ Te has suscrito correctamente.\n\n"
                    "Recibirás alertas sísmicas automáticas de nuevos eventos "
                    "detectados por USGS en todo el mundo.\n\n"
                    "📋 <b>Comandos:</b> /start · /stop · /status · /help\n\n"
                    "🌐 App web: https://sismoalert-pro-since-2026.streamlit.app"
                ))
                print(f"✅ Nuevo suscriptor: {chat_id} ({nombre})")
            else:
                send_message(chat_id, f"✅ {nombre}, ya estás suscrito a SismoAlert Pro.")

        elif command == "/stop":
            if chat_id in subscribers:
                subscribers.discard(chat_id)
                send_message(chat_id, f"😔 {nombre}, has cancelado tu suscripción. Puedes volver con /start.")
                print(f"❌ Suscriptor eliminado: {chat_id} ({nombre})")
            else:
                send_message(chat_id, "No estás suscrito. Usa /start para suscribirte.")

        elif command == "/status":
            send_message(chat_id, (
                f"📊 <b>Estado de SismoAlert Pro</b>\n\n"
                f"👥 Suscriptores activos: <b>{len(subscribers)}</b>\n"
                f"🕐 UTC: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}\n"
                f"🇨🇴 Colombia: {datetime.now(COLOMBIA_TZ).strftime('%d/%m/%Y %H:%M')}\n"
                "📡 Monitor: Activo cada 5 minutos\n"
                "🌐 Fuente de alertas: USGS"
            ))

        elif command == "/help":
            send_message(chat_id, (
                "🌍 <b>SismoAlert Pro — Ayuda</b>\n\n"
                "Alertas sísmicas automáticas mediante USGS, sin filtro de magnitud.\n\n"
                "/start — Suscribirte\n/stop — Cancelar\n/status — Estado\n/help — Ayuda\n\n"
                "🌐 https://sismoalert-pro-since-2026.streamlit.app"
            ))

    state["telegram_update_offset"] = offset
    state["subscribers"] = sorted(subscribers)
    print(f"👥 Suscriptores activos: {len(subscribers)}")
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
    """SGC no se usa en el monitor de Telegram mientras su endpoint FDSN no entregue JSON válido."""
    return []


def check_and_alert(state: dict, subscribers: set) -> dict:
    """Consulta USGS + EMSC y envía alertas a todos los suscriptores."""
    if not subscribers:
        print("Sin suscriptores aún.")
        return state

    now   = datetime.now(timezone.utc)
    start = now - timedelta(minutes=30)

    # Telegram usa USGS como fuente única: cobertura mundial y sin filtro de magnitud.
    # Esto evita enviar dos veces el mismo evento cuando USGS y EMSC reportan el mismo sismo.
    todos = obtener_sismos_usgs(start, now)
    print(f"Total eventos USGS: {len(todos)}")

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
    state = load_state()
    subscribers = load_subscribers(state)

    # Migración segura: conserva los 5 suscriptores que ya están en telegram_alert_state.json.
    state["subscribers"] = sorted(subscribers)
    print(f"Suscriptores activos al iniciar: {len(subscribers)}")

    # 1. Procesar comandos nuevos (/start, /stop, etc.)
    state, subscribers = process_updates(state, subscribers)

    # 2. Consultar USGS y enviar alertas
    state = check_and_alert(state, subscribers)

    # 3. Guardar TODO en el mismo archivo de estado para que GitHub Actions no pierda suscriptores.
    state["subscribers"] = sorted(subscribers)
    save_state(state)
    save_subscribers(subscribers)
    print(f"Estado guardado: {len(subscribers)} suscriptores | {len(state.get('sent', []))} eventos recordados")


if __name__ == "__main__":
    main()
