"""Monitor independiente para SismoAlert Pro.
Consulta USGS y envía alertas a Telegram sin depender de que Streamlit esté abierto.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

STATE_FILE = Path(__file__).with_name("telegram_alert_state.json")
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
TELEGRAM_URL = "https://api.telegram.org/bot{}/sendMessage"

# Umbrales alineados con SismoAlert Pro.
THRESHOLDS = (
    (6.5, "CRÍTICA"),
    (5.5, "ALTA"),
    (4.5, "MEDIA"),
)


def load_state():
    if not STATE_FILE.exists():
        return {"sent": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": []}


def save_state(state):
    # Conservamos solo una ventana razonable para que el archivo no crezca indefinidamente.
    state["sent"] = state.get("sent", [])[-500:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def level_for(magnitude):
    for threshold, label in THRESHOLDS:
        if magnitude >= threshold:
            return label
    return None


def send_telegram(token, chat_id, text):
    response = requests.post(
        TELEGRAM_URL.format(token),
        data={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    response.raise_for_status()


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    now = datetime.now(timezone.utc)
    # GitHub Actions puede iniciar unos minutos tarde; damos margen de 15 min.
    start = now - timedelta(minutes=15)

    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": 4.5,
        "orderby": "time",
        "limit": 100,
    }

    response = requests.get(USGS_URL, params=params, timeout=20)
    response.raise_for_status()
    features = response.json().get("features", [])

    state = load_state()
    sent = set(state.get("sent", []))

    new_ids = []
    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
        event_id = str(feature.get("id") or props.get("ids") or "")
        if not event_id or event_id in sent:
            continue

        magnitude = float(props.get("mag") or 0)
        level = level_for(magnitude)
        if level is None:
            continue

        event_time = datetime.fromtimestamp((props.get("time") or 0) / 1000, tz=timezone.utc)
        place = props.get("place") or "Lugar no informado"
        depth = coords[2] if len(coords) > 2 and coords[2] is not None else 0

        text = (
            "🌍 SismoAlert Pro\n"
            f"🚨 ALERTA {level}\n"
            f"Magnitud: M{magnitude:.1f}\n"
            f"Lugar: {place}\n"
            f"Profundidad: {float(depth):.1f} km\n"
            f"Hora: {event_time.strftime('%d/%m/%Y %H:%M:%S')} UTC\n\n"
            "⚠️ Esta es una notificación automática basada en datos de USGS. "
            "No constituye una predicción de sismos."
        )

        send_telegram(token, chat_id, text)
        new_ids.append(event_id)
        sent.add(event_id)
        print(f"Enviada alerta {level}: M{magnitude:.1f} - {place}")

    state["sent"] = list(sent)
    save_state(state)


if __name__ == "__main__":
    main()
