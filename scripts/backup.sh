#!/usr/bin/env bash
# ============================================
# Messenger — Скрипт бэкапа БД
# ============================================
# Использование: ./scripts/backup.sh
# Бэкапы сохраняются в ./backups/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
DB_FILE="$PROJECT_DIR/data/app.db"
TIMESTAMP="$(date +%F_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/app_${TIMESTAMP}.db"

# Создание директории бэкапов
mkdir -p "$BACKUP_DIR"

# Проверка существования БД
if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: Database file not found: $DB_FILE"
    exit 1
fi

echo "Creating backup: $BACKUP_FILE"

# Бэкап через sqlite3 .backup (безопасный метод)
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"
    echo "Backup created successfully via sqlite3"
else
    # Fallback: копирование с остановкой приложения
    echo "WARNING: sqlite3 not found. Using file copy method."
    echo "Make sure the application is stopped before using this method!"
    cp "$DB_FILE" "$BACKUP_FILE"
    # Копирование WAL и SHM файлов
    [ -f "${DB_FILE}-wal" ] && cp "${DB_FILE}-wal" "${BACKUP_FILE}-wal"
    [ -f "${DB_FILE}-shm" ] && cp "${DB_FILE}-shm" "${BACKUP_FILE}-shm"
    echo "Backup created via file copy"
fi

# Сжатие бэкапа
if command -v gzip &> /dev/null; then
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    echo "Backup compressed: ${BACKUP_FILE}"
fi

# Размер бэкапа
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup size: $BACKUP_SIZE"

# Очистка старых бэкапов (>30 дней)
echo "Cleaning up backups older than 30 days..."
find "$BACKUP_DIR" -name "app_*.db*" -mtime +30 -delete 2>/dev/null || true

echo "Backup complete: $BACKUP_FILE"
