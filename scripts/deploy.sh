#!/usr/bin/env bash
# =============================================================================
# Messenger — Скрипт развёртывания (Docker Compose + хостовой nginx)
# =============================================================================
#
# Описание:
#   Развёртывание мессенджера в Docker контейнерах.
#   НЕ устанавливает ничего на сервер кроме Docker Compose.
#   Настраивает nginx location фрагмент для хостового nginx.
#
# Требования:
#   - Docker + Docker Compose
#   - nginx на хосте (для проксирования)
#   - Домен настроен (A-запись на IP сервера)
#
# Использование:
#   sudo MESSENGER_DOMAIN=gshjis.org \
#        MESSENGER_EMAIL=ilya.togan@gmail.com \
#        bash scripts/deploy.sh
#
# Откат:
#   sudo bash scripts/deploy.sh --rollback
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Загрузка .env файла (если существует в корне проекта)
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Za-z_]+=.' "$ENV_FILE" 2>/dev/null || true)
    set +a
fi

# =============================================================================
# НАСТРАИВАЕМЫЕ ПАРАМЕТРЫ (приоритет: CLI > .env > defaults)
# =============================================================================

# Домен мессенджера
DOMAIN="${MESSENGER_DOMAIN:-YOUR_DOMAIN_HERE}"

# Email для уведомлений
EMAIL="${MESSENGER_EMAIL:-YOUR_EMAIL_HERE}"

# Директории (используем текущую директорию проекта)
INSTALL_DIR="${MESSENGER_INSTALL_DIR:-$PROJECT_DIR}"
LOG_DIR="/var/log/messenger"
NGINX_CONF="/etc/nginx/sites-available/messenger"
NGINX_LINK="/etc/nginx/sites-enabled/messenger"

# Порты (внутренние контейнеры)
BACKEND_PORT=8001
FRONTEND_PORT=9000

# =============================================================================
# КОНСТАНТЫ
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# =============================================================================
# ФУНКЦИИ
# =============================================================================

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()      { echo -e "${GREEN}[ OK ]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

die() {
    log_error "$1"
    exit 1
}

# =============================================================================
# ОТКАТ
# =============================================================================

rollback() {
    log_warn "Начинаю откат..."

    # Остановка контейнеров
    cd "$INSTALL_DIR" 2>/dev/null && docker compose down 2>/dev/null || true

    # Удаление nginx конфига
    rm -f "$NGINX_CONF" "$NGINX_LINK"
    nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

    # Удаление логов
    rm -rf "$LOG_DIR"

    log_ok "Откат завершён"
    exit 0
}

# =============================================================================
# ЭТАП 1: Проверки
# =============================================================================

step_checks() {
    log_info "=== Этап 1: Проверки ==="

    if [ "$(id -u)" -ne 0 ]; then
        die "Требуется root или sudo. Запустите: sudo bash $0"
    fi

    if ! command -v docker &>/dev/null; then
        die "Docker не найден. Установите Docker."
    fi

    if ! docker compose version &>/dev/null; then
        die "Docker Compose не найден. Установите Docker Compose V2."
    fi
    log_ok "Docker: $(docker --version)"
    log_ok "Docker Compose: $(docker compose version)"

    if ! command -v nginx &>/dev/null; then
        log_warn "nginx не найден. Для production нужен хостовой nginx."
    else
        log_ok "nginx: $(nginx -v 2>&1 | cut -d' ' -f3)"
    fi

    if [ "$DOMAIN" = "YOUR_DOMAIN_HERE" ]; then
        die "Укажите MESSENGER_DOMAIN. Запустите: sudo MESSENGER_DOMAIN=gshjis.org bash $0"
    fi
    log_ok "Домен: $DOMAIN"
}

# =============================================================================
# ЭТАП 2: Настройка .env
# =============================================================================

step_env() {
    log_info "=== Этап 2: Настройка .env ==="

    local env_file="${INSTALL_DIR}/.env"

    if [ ! -f "$env_file" ]; then
        log_info "Создание .env..."
        local jwt_secret
        jwt_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)

        cat > "$env_file" <<EOF
# Messenger — Production Configuration
APP_NAME=Messenger
DEBUG=false
LOG_LEVEL=INFO

DATABASE_URL=sqlite+aiosqlite:///./data/app.db

JWT_SECRET_KEY=${jwt_secret}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

UPLOAD_DIR=./data/uploads
MAX_FILE_SIZE_MB=25

RATE_LIMIT_REQUESTS=5
RATE_LIMIT_SECONDS=1

CORS_ORIGINS=https://${DOMAIN}
EOF
        chmod 600 "$env_file"
        log_warn "JWT_SECRET_KEY сгенерирован. Сохраните: ${env_file}"
    else
        log_ok ".env уже существует"
    fi
}

# =============================================================================
# ЭТАП 4: Сборка и запуск контейнеров
# =============================================================================

step_docker() {
    log_info "=== Этап 3: Сборка и запуск контейнеров ==="

    cd "$INSTALL_DIR"

    # Создание директорий
    mkdir -p ./data/uploads ./data/logs
    chmod -R 777 ./data

    # Сборка
    log_info "Сборка образов..."
    docker compose build --no-cache

    # Запуск
    log_info "Запуск контейнеров..."
    docker compose up -d

    # Ожидание
    sleep 5

    # Проверка
    if docker compose ps app | grep -q "Up"; then
        log_ok "Backend запущен"
    else
        log_error "Backend не запустился. Проверьте: docker compose logs app"
    fi

    if docker compose ps frontend | grep -q "Up"; then
        log_ok "Frontend запущен"
    else
        log_error "Frontend не запустился. Проверьте: docker compose logs frontend"
    fi

    # Проверка health
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log_ok "Backend отвечает: http://127.0.0.1:${BACKEND_PORT}/health"
    else
        log_warn "Backend не отвечает (HTTP $http_code). Подождите и проверьте позже."
    fi
}

# =============================================================================
# ЭТАП 5: Настройка nginx location
# =============================================================================

step_nginx() {
    log_info "=== Этап 4: Настройка nginx location ==="

    mkdir -p /etc/nginx/snippets

    # upstream должны быть на уровне http, а не внутри server
    # Создаём upstream файл
    cat > "/etc/nginx/snippets/messenger-upstream.conf" <<EOF
upstream messenger_backend {
    server 127.0.0.1:${BACKEND_PORT};
    keepalive 32;
}

upstream messenger_frontend {
    server 127.0.0.1:${FRONTEND_PORT};
    keepalive 32;
}
EOF

    # Создаём location фрагмент
    cat > "/etc/nginx/snippets/messenger-locations.conf" <<EOF
location /messenger/ {
    proxy_pass http://messenger_frontend/messenger/;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
}

location /messenger/api/ {
    proxy_pass http://messenger_backend/;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
}

location /messenger/ws {
    proxy_pass http://messenger_backend/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;
}

location /messenger/health {
    proxy_pass http://messenger_backend/health;
}
EOF

    # Находим существующий server block
    local main_conf=""
    for conf in /etc/nginx/sites-enabled/*; do
        if [ -f "$conf" ] && grep -q "server_name" "$conf" 2>/dev/null; then
            main_conf="$conf"
            break
        fi
    done

    if [ -n "$main_conf" ]; then
        # Добавляем include в существующий конфиг
        # upstream включаем в nginx.conf на уровне http
        if ! grep -q "messenger-upstream.conf" /etc/nginx/nginx.conf 2>/dev/null; then
            sed -i '/http {/a\    include /etc/nginx/snippets/messenger-upstream.conf;' /etc/nginx/nginx.conf
            log_ok "Upstream добавлен в nginx.conf"
        fi

        if ! grep -q "messenger-locations.conf" "$main_conf" 2>/dev/null; then
            sed -i '/^}$/i\    include /etc/nginx/snippets/messenger-locations.conf;' "$main_conf"
            log_ok "Include добавлен в ${main_conf}"
        fi

        # Добавляем server_name gshjis.org в существующий server block для certbot
        if ! grep -q "server_name.*${DOMAIN}" "$main_conf" 2>/dev/null; then
            # Добавляем gshjis.org к существующему server_name
            sed -i "s/server_name \(.*\);/server_name \1 ${DOMAIN};/" "$main_conf"
            log_ok "Домен ${DOMAIN} добавлен в server_name"
        fi
    else
        log_warn "Не найден существующий nginx конфиг."
        log_warn "Добавьте в nginx.conf (в http блок):"
        log_warn "  include /etc/nginx/snippets/messenger-upstream.conf;"
        log_warn "И в ваш server block:"
        log_warn "  include /etc/nginx/snippets/messenger-locations.conf;"
    fi

    # Тест и перезагрузка nginx
    if command -v nginx &>/dev/null && nginx -t 2>/dev/null; then
        systemctl reload nginx
        log_ok "nginx перезагружен"
    else
        log_warn "nginx -t failed. Проверьте конфиг вручную."
        log_warn "Если есть дубликаты include, удалите их: sudo sed -i '/messenger/d' /etc/nginx/sites-enabled/*"
    fi
}

# =============================================================================
# ЭТАП 6: Логирование
# =============================================================================

step_logging() {
    log_info "=== Этап 5: Настройка логирования ==="

    mkdir -p "$LOG_DIR"

    # Логи контейнеров доступны через docker compose logs
    log_ok "Логи: docker compose logs -f app"
    log_ok "Логи: docker compose logs -f frontend"
}

# =============================================================================
# ЭТАП 6: SSL сертификат (certbot)
# =============================================================================

step_ssl() {
    log_info "=== Этап 6: Проверка/получение SSL сертификата ==="

    local cert_path="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

    if [ -f "$cert_path" ]; then
        log_ok "SSL сертификат уже существует: $cert_path"
        return 0
    fi

    if ! command -v certbot &>/dev/null; then
        log_warn "certbot не найден. SSL нужно настроить вручную:"
        log_warn "  sudo apt-get install -y certbot python3-certbot-nginx"
        log_warn "  sudo certbot --nginx -d ${DOMAIN} --email ${EMAIL}"
        return 0
    fi

    log_info "Запрос SSL сертификата для ${DOMAIN}..."
    if certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --non-interactive; then
        log_ok "SSL сертификат получен"
    else
        log_warn "certbot не смог получить сертификат. Настройте SSL вручную."
    fi
}

# =============================================================================
# ЭТАП 7: Инициализация (первый invite код)
# =============================================================================

step_init() {
    log_info "=== Этап 7: Инициализация ==="

    local db_file="${INSTALL_DIR}/data/app.db"

    if [ ! -f "$db_file" ]; then
        log_warn "База данных не найдена. Пропускаем инициализацию."
        return 0
    fi

    # Проверяем есть ли уже invite коды через Python
    local count
    count=$(python3 -c "
import sqlite3
conn = sqlite3.connect('${db_file}')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM invite_codes')
print(c.fetchone()[0])
conn.close()
" 2>/dev/null || echo "0")

    if [ "$count" -eq 0 ]; then
        # Генерация первого invite кода
        local code
        code=$(python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)))")
        python3 -c "
import sqlite3
conn = sqlite3.connect('${db_file}')
c = conn.cursor()
c.execute(\"INSERT INTO invite_codes (code, max_uses, used_count, is_active, created_at) VALUES ('${code}', 1, 0, 1, datetime('now'))\")
conn.commit()
conn.close()
"
        log_ok "Первый invite код создан: ${code}"
        log_warn "Сохраните его! Он нужен для регистрации первого пользователя."
    else
        log_ok "Invite коды уже существуют"
    fi
}

# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  Messenger — Развёртывание (Docker Compose)"
    echo "=============================================="
    echo ""
    echo "Домен:    ${DOMAIN}"
    echo "Email:    ${EMAIL}"
    echo "Backend:  127.0.0.1:${BACKEND_PORT}"
    echo "Frontend: 127.0.0.1:${FRONTEND_PORT}"
    echo "Директория: ${INSTALL_DIR}"
    echo ""

    # Обработка аргументов
    if [ "${1:-}" = "--rollback" ]; then
        rollback
    fi

    # Этапы
    step_checks
    step_env
    step_docker
    step_nginx
    step_ssl
    step_logging
    step_init

    echo ""
    echo "=============================================="
    echo "  Развёртывание завершено!"
    echo "=============================================="
    echo ""
    echo "  URL:        https://${DOMAIN}/messenger/"
    echo "  Backend:    http://127.0.0.1:${BACKEND_PORT}"
    echo "  Frontend:   http://127.0.0.1:${FRONTEND_PORT}"
    echo ""
    echo "  Следующие шаги:"
    echo "  1. Добавьте location блоки из ${NGINX_CONF} в ваш nginx server block"
    echo "  2. sudo nginx -t && sudo systemctl reload nginx"
    echo "  3. Проверьте: curl https://${DOMAIN}/messenger/health"
    echo ""
    echo "  Управление:"
    echo "    cd ${INSTALL_DIR}"
    echo "    docker compose logs -f app"
    echo "    docker compose restart"
    echo "    docker compose down"
    echo ""
    echo "  Откат: sudo bash $0 --rollback"
    echo ""
}

main "$@"

