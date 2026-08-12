"""
Monitor mundial independiente para SismoAlert Pro.

Consulta USGS y envía a Telegram todos los eventos nuevos
disponibles en la ventana de consulta, sin filtro de magnitud.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


STATE_FILE = Path(__file__).with_name("telegram_alert_state.json")

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
TELEGRAM_URL = "https://api.telegram.org/bot{}/sendMessage"
TELEGRAM_UPDATES_URL = "https://api.telegram.org/bot{}/getUpdates"

# Hora oficial de Colombia
COLOMBIA_TZ = ZoneInfo("America/Bogota")


def load_state():
    """Carga el estado de sismos y suscriptores de Telegram."""
    if not STATE_FILE.exists():
        return {
            "sent": [],
            "subscribers": [],
            "telegram_update_offset": 0,
        }

    try:
        state = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        state.setdefault("sent", [])
        state.setdefault("subscribers", [])
        state.setdefault("telegram_update_offset", 0)
        return state
    except Exception:
        return {
            "sent": [],
            "subscribers": [],
            "telegram_update_offset": 0,
        }

def save_state(state):
    """Conserva los últimos 500 sismos y los suscriptores activos."""
    state["sent"] = state.get("sent", [])[-500:]
    state["subscribers"] = list(dict.fromkeys(
        str(chat_id) for chat_id in state.get("subscribers", [])
    ))
    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

def send_telegram(token, chat_id, text):
    """Envía un mensaje a Telegram."""
    response = requests.post(
        TELEGRAM_URL.format(token),
        data={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=15,
    )

    response.raise_for_status()



def get_updates(token, offset):
    """Obtiene mensajes nuevos del bot para detectar /start y /stop."""
    response = requests.get(
        TELEGRAM_UPDATES_URL.format(token),
        params={
            "offset": offset or None,
            "timeout": 5,
            "allowed_updates": json.dumps(["message"]),
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            data.get("description", "Telegram getUpdates falló")
        )

    return data.get("result", [])


def update_subscribers(token, state):
    """
    Registra automáticamente a cualquier persona/chat que envíe /start.
    También permite /stop para dejar de recibir alertas.
    """
    subscribers = set(
        str(chat_id) for chat_id in state.get("subscribers", [])
    )

    # Conservamos el chat principal que ya funcionaba.
    legacy_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if legacy_chat_id:
        subscribers.add(str(legacy_chat_id))

    offset = int(state.get("telegram_update_offset", 0) or 0)

    try:
        updates = get_updates(token, offset)
    except Exception as error:
        print(
            "⚠️ No se pudieron consultar nuevos suscriptores de Telegram: "
            f"{error}"
        )
        state["subscribers"] = list(subscribers)
        return

    for update in updates:
        update_id = update.get("update_id")
        if update_id is not None:
            offset = max(offset, int(update_id) + 1)

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()

        if chat_id is None:
            continue

        command = (
            text.split()[0].split("@")[0].lower()
            if text else ""
        )

        if command == "/start":
            chat_id_text = str(chat_id)
            is_new = chat_id_text not in subscribers
            subscribers.add(chat_id_text)

            if is_new:
                try:
                    send_telegram(
                        token,
                        chat_id_text,
                        "🌍 SismoAlert Pro\n\n"
                        "✅ Te has suscrito correctamente.\n"
                        "Recibirás las alertas sísmicas automáticas "
                        "cuando se detecten nuevos eventos.\n\n"
                        "Para dejar de recibirlas, escribe /stop."
                    )
                    print(f"👤 Nuevo suscriptor: {chat_id_text}")
                except Exception as error:
                    print(
                        f"⚠️ Se registró {chat_id_text}, "
                        f"pero no se pudo enviar el mensaje de bienvenida: "
                        f"{error}"
                    )

        elif command == "/stop":
            chat_id_text = str(chat_id)
            if chat_id_text in subscribers:
                subscribers.remove(chat_id_text)
                print(f"👋 Suscriptor eliminado: {chat_id_text}")

    state["telegram_update_offset"] = offset
    state["subscribers"] = list(subscribers)
    print(f"👥 Suscriptores activos: {len(subscribers)}")


def main():

    token = os.environ["TELEGRAM_BOT_TOKEN"]

    # Registrar automáticamente a quienes hayan enviado /start.
    state = load_state()
    update_subscribers(token, state)
    subscribers = set(
        str(chat_id) for chat_id in state.get("subscribers", [])
    )

    # Hora actual en UTC
    now = datetime.now(timezone.utc)

    # Consultamos los últimos 15 minutos.
    # Esto da margen si GitHub Actions se retrasa.
    start = now - timedelta(minutes=15)

    params = {
        "format": "geojson",
        "starttime": start.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "endtime": now.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),

        # IMPORTANTE:
        # NO hay minmagnitude.
        # Por lo tanto se reciben eventos
        # de cualquier magnitud disponible.

        "orderby": "time",

        "limit": 20000,
    }

    response = requests.get(
        USGS_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    features = response.json().get(
        "features",
        []
    )

    print(
        f"Eventos encontrados por USGS: {len(features)}"
    )

    sent = set(
        state.get("sent", [])
    )

    nuevos = 0

    for feature in features:

        properties = feature.get(
            "properties",
            {}
        )

        geometry = feature.get(
            "geometry",
            {}
        )

        coordinates = geometry.get(
            "coordinates",
            [None, None, None]
        )

        event_id = str(
            feature.get("id")
            or properties.get("ids")
            or ""
        )

        # Sin ID no podemos controlar duplicados.
        if not event_id:
            continue

        # Ya fue enviado.
        if event_id in sent:
            continue

        magnitude_value = properties.get(
            "mag"
        )

        if magnitude_value is None:
            magnitude_text = "No disponible"
        else:
            try:
                magnitude = float(
                    magnitude_value
                )
                magnitude_text = f"M{magnitude:.1f}"
            except Exception:
                magnitude_text = str(
                    magnitude_value
                )

        # Hora del evento
        event_timestamp = properties.get(
            "time"
        )

        if event_timestamp:

            event_time_utc = datetime.fromtimestamp(
                event_timestamp / 1000,
                tz=timezone.utc
            )

            event_time_colombia = (
                event_time_utc.astimezone(
                    COLOMBIA_TZ
                )
            )

            hora_colombia = (
                event_time_colombia.strftime(
                    "%d/%m/%Y %I:%M:%S %p"
                )
            )

            hora_utc = (
                event_time_utc.strftime(
                    "%d/%m/%Y %H:%M:%S UTC"
                )
            )

        else:

            hora_colombia = "No disponible"
            hora_utc = "No disponible"

        place = properties.get(
            "place"
        ) or "Lugar no informado"

        # Profundidad
        depth = (
            coordinates[2]
            if len(coordinates) > 2
            and coordinates[2] is not None
            else None
        )

        if depth is not None:

            try:
                depth_text = (
                    f"{float(depth):.1f} km"
                )
            except Exception:
                depth_text = str(depth)

        else:
            depth_text = "No disponible"

        # Mensaje Telegram
        text = (
            "🌍 SismoAlert Pro\n"
            "🔔 NUEVO SISMO DETECTADO\n\n"
            f"📏 Magnitud: {magnitude_text}\n"
            f"📍 Lugar: {place}\n"
            f"⬇️ Profundidad: {depth_text}\n\n"
            f"🇨🇴 Hora Colombia: {hora_colombia}\n"
            f"🌐 Hora UTC: {hora_utc}\n\n"
            "⚠️ Notificación automática basada "
            "en datos de USGS.\n"
            "No constituye una predicción de sismos."
        )

        enviados_evento = 0
        suscriptores_invalidos = []

        for subscriber_id in list(subscribers):
            try:
                send_telegram(
                    token,
                    subscriber_id,
                    text
                )
                enviados_evento += 1

            except requests.HTTPError as error:
                status_code = getattr(
                    error.response,
                    "status_code",
                    None
                )
                if status_code in (400, 403):
                    suscriptores_invalidos.append(subscriber_id)
                    print(
                        f"⚠️ Se elimina suscriptor {subscriber_id}: "
                        f"Telegram respondió HTTP {status_code}"
                    )
                else:
                    print(
                        f"❌ Error enviando a {subscriber_id}: {error}"
                    )

            except Exception as error:
                print(
                    f"❌ Error enviando a {subscriber_id}: {error}"
                )

        for subscriber_id in suscriptores_invalidos:
            subscribers.discard(subscriber_id)

        state["subscribers"] = list(subscribers)

        if enviados_evento > 0:
            sent.add(event_id)
            nuevos += 1
            print(
                f"✅ Sismo enviado a {enviados_evento} "
                f"chat(s): {magnitude_text} - {place}"
            )
        else:
            print(
                f"⚠️ No se pudo enviar el sismo a ningún suscriptor: "
                f"{magnitude_text} - {place}"
            )

    state["sent"] = list(sent)

    save_state(state)

    print(
        f"Alertas nuevas enviadas: {nuevos}"
    )


if __name__ == "__main__":
    main()
