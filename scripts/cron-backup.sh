#!/usr/bin/env bash
# ============================================
# Messenger — Cron-скрипт для автобэкапов
# ============================================
# Добавить в crontab: 0 2 * * * /path/to/scripts/cron-backup.sh
# (ежедневно в 2:00)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/backups/backup-cron.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting scheduled backup..." >> "$LOG_FILE"

# Запуск бэкапа
if "$SCRIPT_DIR/backup.sh" >> "$LOG_FILE" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completed successfully" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Backup failed!" >> "$LOG_FILE"
    # Отправка уведомления (если настроен Telegram бот)
    # curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" \
    #     -d "chat_id=<CHAT_ID>" \
    #     -d "text=⚠️ Messenger backup failed!" > /dev/null 2>&1
fi
