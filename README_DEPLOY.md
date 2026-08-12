# SismoAlert Pro — despliegue y Telegram

## 1. Streamlit Community Cloud
1. Sube este proyecto a un repositorio de GitHub.
2. Entra a Streamlit Community Cloud y crea una app seleccionando `app.py`.
3. En **App settings → Secrets**, pega:

```toml
telegram_bot_token = "TU_TOKEN_NUEVO"
telegram_chat_id = "949371440"
```

No subas `secrets.toml` al repositorio.

## 2. Telegram aunque la página esté cerrada
El archivo `telegram_monitor.py` consulta USGS de forma independiente.
El workflow `.github/workflows/telegram-alerts.yml` se ejecuta cada 5 minutos y usa los secretos de GitHub:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

En GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

## 3. Estado de alertas
`telegram_alert_state.json` se actualiza por GitHub Actions para evitar enviar dos veces el mismo evento USGS.

## 4. Importante
El token que fue compartido en el chat debe revocarse y regenerarse en BotFather antes de publicar el proyecto. El código no contiene el token real.
