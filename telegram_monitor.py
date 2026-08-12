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

# Zona horaria de Colombia
COLOMBIA_TZ = ZoneInfo("America/Bogota")


def load_state():
    """Carga los IDs de sismos que ya fueron enviados."""
    if not STATE_FILE.exists():
        return {"sent": []}

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {"sent": []}


def save_state(state):
    """Guarda solamente los últimos 500 IDs para evitar crecimiento infinito."""
    state["sent"] = state.get("sent", [])[-500:]

    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def send_telegram(token, chat_id, text):
    """Envía el mensaje a Telegram."""
    response = requests.post(
        TELEGRAM_URL.format(token),
        data={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=15,
    )

    response.raise_for_status()


def main():

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    # Hora actual en UTC
    now = datetime.now(timezone.utc)

    # GitHub Actions normalmente se ejecuta cada 5 minutos.
    # Dejamos 15 minutos de margen para evitar perder eventos
    # si una ejecución se retrasa.
    start = now - timedelta(minutes=15)

    params = {
        "format": "geojson",

        "starttime": start.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),

        "endtime": now.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),

        # SIN minmagnitude:
        # se reciben eventos de cualquier magnitud disponible.

        "orderby": "time",

        # Máximo permitido por la API de USGS.
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

    state = load_state()

    sent = set(
        state.get("sent", [])
    )

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

        # Si no tiene ID no podemos controlar duplicados.
        if not event_id:
            continue

        # No volver a mandar un sismo ya enviado.
        if event_id in sent:
            continue

        magnitude_value = properties.get(
            "mag"
        )

        # Algunos eventos pueden no tener magnitud.
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

        # Hora original del evento en UTC.
        event_timestamp = properties.get(
            "time"
        )

        if event_timestamp:
            event_time_utc = datetime.fromtimestamp(
                event_timestamp / 1000,
                tz=timezone.utc
            )

            # Conversión a hora de Colombia.
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

        try:

            send_telegram(
                token,
                chat_id,
                text
            )

            sent.add(event_id)

            print(
                f"Sismo enviado: "
                f"{magnitude_text} - {place}"
            )

        except Exception as error:

            print(
                f"Error enviando "
                f"{event_id}: {error}"
            )

    state["sent"] = list(sent)

    save_state(state)


if __name__ == "__main__":
    main()
