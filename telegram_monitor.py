"""SismoAlert Pro - Monitor sísmico + bot Telegram.

Fuentes: USGS + EMSC + SGC Colombia.
Ventana: últimas 2 horas.
Los reportes del mismo terremoto se deduplican antes de enviar.
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EMSC_URL = "https://www.seismicportal.eu/fdsnws/event/1/query"
SGC_URL = ("https://srvags.sgc.gov.co/arcgis/rest/services/"
           "catalogo_sismos/catalogo_de_sismos_2/MapServer/0/query")
BOT_URL = f"https://api.telegram.org/bot{TOKEN}"
COLOMBIA_TZ = ZoneInfo("America/Bogota")
STATE_FILE = Path(__file__).with_name("telegram_alert_state.json")
SUBSCRIBERS_FILE = Path(__file__).with_name("telegram_subscribers.json")


def load_state():
    if not STATE_FILE.exists():
        return {"sent": [], "subscribers": [], "telegram_update_offset": 0}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        state.setdefault("sent", [])
        state.setdefault("subscribers", [])
        state.setdefault("telegram_update_offset", state.get("last_update_id", 0))
        return state
    except Exception:
        return {"sent": [], "subscribers": [], "telegram_update_offset": 0}


def save_state(state):
    state["sent"] = list(dict.fromkeys(state.get("sent", [])))[-500:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_subscribers(state):
    subscribers = {str(x) for x in state.get("subscribers", [])}
    if SUBSCRIBERS_FILE.exists():
        try:
            data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            subscribers.update(str(x) for x in data.get("subscribers", []))
        except Exception:
            pass
    legacy = os.environ.get("TELEGRAM_CHAT_ID")
    if legacy:
        subscribers.add(str(legacy))
    return subscribers


def save_subscribers(subs):
    try:
        SUBSCRIBERS_FILE.write_text(
            json.dumps({"subscribers": sorted(subs)}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"⚠️ No se pudo guardar suscriptores: {exc}")


def send_message(chat_id, text):
    try:
        r = requests.post(
            f"{BOT_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as exc:
        print(f"⚠️ Error Telegram {chat_id}: {exc}")
        return False


def get_updates(offset=0):
    try:
        r = requests.get(
            f"{BOT_URL}/getUpdates",
            params={"offset": offset, "timeout": 5, "limit": 100},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("result", [])
        print(f"⚠️ Telegram getUpdates HTTP {r.status_code}")
    except Exception as exc:
        print(f"⚠️ Error getUpdates: {exc}")
    return []


def process_updates(state, subscribers):
    offset = int(state.get("telegram_update_offset", 0) or 0)
    for update in get_updates(offset):
        uid = update.get("update_id")
        if uid is not None:
            offset = max(offset, int(uid) + 1)
        msg = update.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = (msg.get("text") or "").strip()
        name = chat.get("first_name") or "amigo"
        if not chat_id:
            continue
        command = text.split()[0].split("@")[0].lower() if text else ""
        if command == "/start":
            new = chat_id not in subscribers
            subscribers.add(chat_id)
            if new:
                send_message(chat_id, f"🌍 <b>¡Hola {name}! Bienvenido a SismoAlert Pro</b>\n\n"
                             "✅ Te has suscrito correctamente.\n\n"
                             "Recibirás alertas de nuevos sismos detectados por USGS, EMSC y SGC.\n\n"
                             "📋 /start · /stop · /status · /help\n\n"
                             "🌐 App: https://sismoalert-pro-since-2026.streamlit.app")
                print(f"✅ Nuevo suscriptor: {chat_id} ({name})")
            else:
                send_message(chat_id, f"✅ {name}, ya estás suscrito a SismoAlert Pro.")
        elif command == "/stop":
            if chat_id in subscribers:
                subscribers.discard(chat_id)
                send_message(chat_id, f"😔 {name}, has cancelado tu suscripción. Puedes volver con /start.")
                print(f"❌ Suscriptor eliminado: {chat_id}")
            else:
                send_message(chat_id, "No estás suscrito. Usa /start para suscribirte.")
        elif command == "/status":
            send_message(chat_id, "📊 <b>SismoAlert Pro</b>\n\n"
                         f"👥 Suscriptores: <b>{len(subscribers)}</b>\n"
                         f"🕐 UTC: {datetime.now(timezone.utc):%d/%m/%Y %H:%M}\n"
                         f"🇨🇴 Colombia: {datetime.now(COLOMBIA_TZ):%d/%m/%Y %I:%M %p}\n"
                         "📡 Fuentes: USGS + EMSC + SGC\n"
                         "⏱️ Ventana: 2 horas")
        elif command == "/help":
            send_message(chat_id, "🌍 <b>SismoAlert Pro — Ayuda</b>\n\n"
                         "Alertas automáticas mediante USGS, EMSC y SGC.\n"
                         "Se revisan las últimas 2 horas en cada ejecución.\n\n"
                         "/start — Suscribirte\n/stop — Cancelar\n/status — Estado\n/help — Ayuda")
    state["telegram_update_offset"] = offset
    state["subscribers"] = sorted(subscribers)
    print(f"👥 Suscriptores activos: {len(subscribers)}")
    return state, subscribers


def safe_float(value):
    try:
        return None if value is None or value == "" else float(value)
    except Exception:
        return None


def to_timestamp_ms(value):
    if value is None or value == "":
        return None
    try:
        n = float(value)
        if n > 100_000_000_000:
            return int(n)
        if n > 1_000_000_000:
            return int(n * 1000)
    except Exception:
        pass
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except Exception:
            return None
    return None


def normalize(e):
    return {
        "id": str(e.get("id") or ""),
        "mag": safe_float(e.get("mag")),
        "place": e.get("place") or "Lugar no informado",
        "time": to_timestamp_ms(e.get("time")),
        "depth": safe_float(e.get("depth")),
        "lat": safe_float(e.get("lat")),
        "lon": safe_float(e.get("lon")),
        "fuente": e.get("fuente") or "Desconocida",
    }


def obtener_sismos_usgs(start, now):
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby": "time",
        "minmagnitude": 0.0,
        "limit": 20000,
    }
    try:
        r = requests.get(USGS_URL, params=params, timeout=30)
        r.raise_for_status()
        events = []
        for f in r.json().get("features", []):
            if not f.get("id"):
                continue
            p = f.get("properties") or {}
            g = f.get("geometry") or {}
            c = g.get("coordinates") or [None, None, None]
            events.append({
                "id": f"usgs_{f['id']}", "mag": p.get("mag"),
                "place": p.get("place") or "Lugar no informado",
                "time": p.get("time"), "depth": c[2] if len(c) > 2 else None,
                "lat": c[1] if len(c) > 1 else None, "lon": c[0] if c else None,
                "fuente": "USGS",
            })
        print(f"USGS: {len(events)} eventos")
        return events
    except Exception as exc:
        print(f"⚠️ Error USGS: {exc}")
        return []


def obtener_sismos_emsc(start, now):
    params = {
        "format": "json",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby": "time", "minmag": 0.0, "limit": 1000,
    }
    try:
        r = requests.get(EMSC_URL, params=params, timeout=30)
        r.raise_for_status()
        events = []
        for f in r.json().get("features", []):
            p = f.get("properties") or {}
            g = f.get("geometry") or {}
            c = g.get("coordinates") or [None, None, None]
            eid = str(f.get("id") or p.get("unid") or "")
            if not eid:
                continue
            events.append({
                "id": f"emsc_{eid}", "mag": p.get("mag"),
                "place": p.get("flynn_region") or p.get("place") or "Lugar no informado",
                "time": p.get("time"), "depth": c[2] if len(c) > 2 else None,
                "lat": c[1] if len(c) > 1 else None, "lon": c[0] if c else None,
                "fuente": "EMSC",
            })
        print(f"EMSC: {len(events)} eventos")
        return events
    except Exception as exc:
        print(f"⚠️ Error EMSC: {exc}")
        return []


def obtener_sismos_sgc(start, now):
    """Consulta el catálogo sísmico oficial del SGC vía ArcGIS REST."""
    params = {
        "where": "1=1", "outFields": "*", "returnGeometry": "true",
        "orderByFields": "ESP_FECHA_LONG DESC", "resultRecordCount": 1000,
        "f": "json",
    }
    try:
        r = requests.get(SGC_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            print(f"⚠️ SGC respondió con error: {data['error']}")
            return []
        start_ms = int(start.timestamp() * 1000)
        now_ms = int(now.timestamp() * 1000)
        events = []
        for f in data.get("features", []):
            a = f.get("attributes") or {}
            g = f.get("geometry") or {}
            ts = to_timestamp_ms(a.get("ESP_FECHA_LONG"))
            if ts is None or ts < start_ms or ts > now_ms:
                continue
            eid = a.get("ESP_ID_EVENTO_TXT") or a.get("OBJECTID")
            if eid is None:
                continue
            lat = g.get("y") if g.get("y") is not None else a.get("ESP_LATITUD")
            lon = g.get("x") if g.get("x") is not None else a.get("ESP_LONGITUD")
            events.append({
                "id": f"sgc_{eid}",
                "mag": a.get("ESP_MAGNITUD") if a.get("ESP_MAGNITUD") is not None else a.get("RR_MAG"),
                "place": "Colombia",
                "time": ts,
                "depth": a.get("ESP_PROFUNDIDAD"),
                "lat": lat, "lon": lon,
                "fuente": "SGC",
            })
        print(f"SGC: {len(events)} eventos")
        return events
    except ValueError as exc:
        print(f"⚠️ SGC devolvió una respuesta no JSON válida: {exc}")
        return []
    except requests.RequestException as exc:
        print(f"⚠️ Error de conexión con SGC: {exc}")
        return []
    except Exception as exc:
        print(f"⚠️ Error SGC: {exc}")
        return []


def distance_km(a, b):
    if None in (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon")):
        return None
    try:
        r = 6371.0
        p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
        dp = math.radians(b["lat"] - a["lat"])
        dl = math.radians(b["lon"] - a["lon"])
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(h))
    except Exception:
        return None


def same_event(a, b):
    if a.get("time") is None or b.get("time") is None:
        return False
    if abs(a["time"] - b["time"]) > 180000:
        return False
    if a.get("mag") is not None and b.get("mag") is not None and abs(a["mag"] - b["mag"]) > 0.5:
        return False
    d = distance_km(a, b)
    return d is None or d <= 100


def combine_events(events):
    combined = []
    for raw in sorted((normalize(e) for e in events), key=lambda x: x.get("time") or 0):
        if not raw["id"]:
            continue
        found = next((x for x in combined if same_event(x, raw)), None)
        if found is None:
            raw["fuentes"] = [raw["fuente"]]
            raw["source_ids"] = [raw["id"]]
            combined.append(raw)
            continue
        if raw["fuente"] not in found["fuentes"]:
            found["fuentes"].append(raw["fuente"])
        found["source_ids"].append(raw["id"])
        if found.get("mag") is None:
            found["mag"] = raw.get("mag")
        if found.get("depth") is None:
            found["depth"] = raw.get("depth")
        if found.get("lat") is None:
            found["lat"] = raw.get("lat")
        if found.get("lon") is None:
            found["lon"] = raw.get("lon")
    return combined


def event_key(e):
    if e.get("time") is None:
        return None
    try:
        bucket = int((e["time"] // 1000) / 180)
        lat = "NA" if e.get("lat") is None else f"{e['lat']:.1f}"
        lon = "NA" if e.get("lon") is None else f"{e['lon']:.1f}"
        mag = "NA" if e.get("mag") is None else f"{e['mag']:.1f}"
        return f"event_{bucket}_{lat}_{lon}_{mag}"
    except Exception:
        return None


def check_and_alert(state, subscribers):
    if not subscribers:
        print("Sin suscriptores aún.")
        return state
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=2)
    print(f"🕐 Ventana: {start:%Y-%m-%d %H:%M:%S UTC} → {now:%Y-%m-%d %H:%M:%S UTC}")

    usgs = obtener_sismos_usgs(start, now)
    emsc = obtener_sismos_emsc(start, now)
    sgc = obtener_sismos_sgc(start, now)
    all_events = usgs + emsc + sgc
    print(f"Total antes de deduplicar: {len(all_events)}")
    events = combine_events(all_events)
    print(f"Total después de deduplicar: {len(events)}")

    sent = {str(x) for x in state.get("sent", [])}
    new_count = 0
    for e in events:
        eid = e["id"]
        key = event_key(e)
        if eid in sent or (key and key in sent):
            continue
        mag = e.get("mag")
        place = e.get("place") or "Lugar no informado"
        depth = e.get("depth")
        ts = e.get("time")
        mag_text = f"M{mag:.1f}" if mag is not None else "N/D"
        depth_text = f"{depth:.1f} km" if depth is not None else "N/D"
        if ts is not None:
            utc_t = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            col_t = utc_t.astimezone(COLOMBIA_TZ)
            utc_text = utc_t.strftime("%d/%m/%Y %H:%M UTC")
            col_text = col_t.strftime("%d/%m/%Y %I:%M %p")
        else:
            utc_text = col_text = "No disponible"
        m = mag or 0
        if m >= 7:
            emoji, level = "🚨🚨🚨", "CRÍTICO"
        elif m >= 6:
            emoji, level = "🔴🔴", "ALTO"
        elif m >= 5:
            emoji, level = "🟠", "MODERADO"
        elif m >= 4:
            emoji, level = "🟡", "LEVE"
        else:
            emoji, level = "🟢", "MENOR"
        sources = " + ".join(e.get("fuentes", [])) or e.get("fuente", "Desconocida")
        message = (f"{emoji} <b>SISMO {level} — {mag_text}</b>\n\n"
                   f"📍 <b>Lugar:</b> {place}\n"
                   f"⬇️ <b>Profundidad:</b> {depth_text}\n"
                   f"🌐 <b>UTC:</b> {utc_text}\n"
                   f"🇨🇴 <b>Colombia:</b> {col_text}\n"
                   f"📡 <b>Fuentes:</b> {sources}\n\n"
                   "🌐 Ver en app: https://sismoalert-pro-since-2026.streamlit.app")
        sent_ok = 0
        failed = []
        for cid in list(subscribers):
            if send_message(cid, message):
                sent_ok += 1
            else:
                failed.append(cid)
        for cid in failed:
            subscribers.discard(cid)
            print(f"⚠️ Suscriptor eliminado (bot bloqueado): {cid}")
        if sent_ok > 0:
            sent.add(eid)
            if key:
                sent.add(key)
            save_subscribers(subscribers)
            new_count += 1
            print(f"✅ Alerta enviada a {sent_ok} personas: {mag_text} — {place} [{sources}]")
        else:
            print(f"⚠️ No se pudo enviar: {mag_text} — {place}")
    state["sent"] = list(sent)[-500:]
    state["subscribers"] = sorted(subscribers)
    print(f"Alertas nuevas enviadas: {new_count} | Suscriptores: {len(subscribers)}")
    return state


def main():
    state = load_state()
    subscribers = load_subscribers(state)
    state["subscribers"] = sorted(subscribers)
    print(f"Suscriptores activos al iniciar: {len(subscribers)}")
    state, subscribers = process_updates(state, subscribers)
    state = check_and_alert(state, subscribers)
    state["subscribers"] = sorted(subscribers)
    save_state(state)
    save_subscribers(subscribers)
    print(f"Estado guardado: {len(subscribers)} suscriptores | {len(state.get('sent', []))} identificadores recordados")


if __name__ == "__main__":
    main()
