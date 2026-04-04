#!/usr/bin/env bash
# ============================================
# Messenger — Скрипт восстановления БД
# ============================================
# Использование: ./scripts/restore.sh <backup_file>
# Пример: ./scripts/restore.sh ./backups/app_2024-01-01_120000.db.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_FILE="$PROJECT_DIR/data/app.db"

# Проверка аргументов
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -la "$PROJECT_DIR/backups/" 2>/dev/null || echo "  No backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Проверка существования бэкапа
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Предупреждение
echo "WARNING: This will overwrite the current database!"
echo "Current database: $DB_FILE"
echo "Backup file: $BACKUP_FILE"
echo ""
read -p "Are you sure? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 1
fi

# Остановка приложения
echo "Stopping application..."
cd "$PROJECT_DIR"
docker compose down 2>/dev/null || true

# Распаковка если нужно
TEMP_FILE="$BACKUP_FILE"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing backup..."
    TEMP_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
fi

# Создание директории
mkdir -p "$(dirname "$DB_FILE")"

# Восстановление
echo "Restoring database..."
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_FILE" ".restore '$TEMP_FILE'"
    echo "Database restored successfully via sqlite3"
else
    cp "$TEMP_FILE" "$DB_FILE"
    echo "Database restored via file copy"
fi

# Очистка временных файлов
if [ "$TEMP_FILE" != "$BACKUP_FILE" ] && [ -f "$TEMP_FILE" ]; then
    rm -f "$TEMP_FILE"
fi

# Настройка WAL режима
if command -v sqlite3 &> /dev/null; then
    echo "Setting WAL mode..."
    sqlite3 "$DB_FILE" "PRAGMA journal_mode=WAL;"
    sqlite3 "$DB_FILE" "PRAGMA synchronous=NORMAL;"
    sqlite3 "$DB_FILE" "PRAGMA foreign_keys=ON;"
fi

# Запуск приложения
echo "Starting application..."
cd "$PROJECT_DIR"
docker compose up -d

echo "Restore complete!"
