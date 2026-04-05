#!/usr/bin/env bash
# =============================================================================
# Messenger — Скрипт инициализации (создание первого invite кода)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Загрузка .env
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source <(grep -E '^[A-Za-z_]+=.' "$ENV_FILE" 2>/dev/null || true)
    set +a
fi

INSTALL_DIR="${MESSENGER_INSTALL_DIR:-$PROJECT_DIR}"
DB_FILE="${INSTALL_DIR}/data/app.db"

# Генерация invite кода
CODE=$(python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(${INVITE_CODE_LENGTH:-8})))")

echo "=============================================="
echo "  Messenger — Инициализация"
echo "=============================================="
echo ""

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: База данных не найдена: $DB_FILE"
    echo "Сначала запустите: bash scripts/deploy.sh"
    exit 1
fi

# Создание invite кода
sqlite3 "$DB_FILE" "INSERT INTO invite_codes (code, max_uses, used_count, is_active, created_at) VALUES ('${CODE}', 1, 0, 1, datetime('now'));"

echo ""
echo "  Invite код создан: ${CODE}"
echo ""
echo "  Используйте его для регистрации первого пользователя:"
echo "  https://gshjis.org/messenger/"
echo ""
