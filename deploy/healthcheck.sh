#!/bin/bash
# Health-check + auto-restart + Telegram alert for Silent Couple Bot
# Runs every 2 minutes via cron.
# State files in /tmp keep track of previous states to avoid duplicate alerts.

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
ENV_FILE="/home/telegram-bot/.env"
HEALTH_URL="http://127.0.0.1:8444/health"
SERVICES=("nginx" "silent-couple-bot-webhook" "silent-couple-bot-worker")
STATE_DIR="/tmp/sbc_healthcheck"
LOG_FILE="/var/log/sbc_healthcheck.log"

# ── Load credentials from .env ────────────────────────────────────────────────
BOT_TOKEN=""
ADMIN_CHAT_ID=""

if [[ -f "$ENV_FILE" ]]; then
    BOT_TOKEN=$(grep -E '^TG_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]"')
    ADMIN_CHAT_ID=$(grep -E '^ADMIN_TG_ID=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]"')
fi

if [[ -z "$BOT_TOKEN" || -z "$ADMIN_CHAT_ID" ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] BOT_TOKEN or ADMIN_CHAT_ID not found in $ENV_FILE" >> "$LOG_FILE"
    exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
mkdir -p "$STATE_DIR"

send_alert() {
    local text="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S %Z')
    local message="⚠️ *Silent Couple Bot Monitor*%0A${text}%0A_%0A${timestamp}_"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ADMIN_CHAT_ID}&text=${message}&parse_mode=Markdown" \
        -o /dev/null --max-time 10 || true
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ALERT] ${text}" >> "$LOG_FILE"
}

send_recovery() {
    local text="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S %Z')
    local message="✅ *Silent Couple Bot Monitor*%0A${text}%0A_%0A${timestamp}_"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ADMIN_CHAT_ID}&text=${message}&parse_mode=Markdown" \
        -o /dev/null --max-time 10 || true
    echo "$(date '+%Y-%m-%d %H:%M:%S') [RECOVERY] ${text}" >> "$LOG_FILE"
}

state_file() {
    echo "${STATE_DIR}/$(echo "$1" | tr ' /' '_').state"
}

was_down() {
    [[ -f "$(state_file "$1")" ]]
}

mark_down() {
    touch "$(state_file "$1")"
}

mark_up() {
    rm -f "$(state_file "$1")"
}

# ── Check services ────────────────────────────────────────────────────────────
for service in "${SERVICES[@]}"; do
    if ! systemctl is-active --quiet "$service"; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] $service is down, restarting..." >> "$LOG_FILE"
        systemctl restart "$service" || true
        sleep 3

        if systemctl is-active --quiet "$service"; then
            if was_down "$service"; then
                send_recovery "Сервис \`${service}\` упал и был *автоматически перезапущен*."
                mark_up "$service"
            else
                send_alert "Сервис \`${service}\` был остановлен и *автоматически перезапущен*."
            fi
        else
            if ! was_down "$service"; then
                send_alert "Сервис \`${service}\` *упал и НЕ поднялся*. Требуется ручное вмешательство!"
                mark_down "$service"
            fi
        fi
    else
        if was_down "$service"; then
            send_recovery "Сервис \`${service}\` снова работает нормально."
            mark_up "$service"
        fi
    fi
done

# ── Check HTTP health endpoint ────────────────────────────────────────────────
HEALTH_KEY="http_health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" || echo "000")

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] Health endpoint returned HTTP ${HTTP_CODE}" >> "$LOG_FILE"
    if ! was_down "$HEALTH_KEY"; then
        send_alert "Health endpoint \`${HEALTH_URL}\` вернул HTTP *${HTTP_CODE}*. Webhook может не принимать запросы от Telegram."
        mark_down "$HEALTH_KEY"
    fi
else
    if was_down "$HEALTH_KEY"; then
        send_recovery "Health endpoint снова отвечает *200 OK*. Бот принимает запросы."
        mark_up "$HEALTH_KEY"
    fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') [OK] healthcheck done (HTTP ${HTTP_CODE})" >> "$LOG_FILE"
