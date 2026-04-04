#!/usr/bin/env bash
# =============================================================================
# Messenger — Скрипт развёртывания на VPS (Ubuntu + systemd + nginx)
# =============================================================================
#
# Описание:
#   Автоматическая установка и настройка мессенджера на Ubuntu VPS.
#   Настраивает nginx как reverse proxy, systemd-юниты, HTTPS, логирование.
#   НЕ затрагивает существующие конфигурации nginx и VPN.
#
# Требования:
#   - Ubuntu 20.04+
#   - Root или sudo доступ
#   - nginx уже установлен и работает
#   - Домен настроен (A-запись на IP сервера)
#
# Использование:
#   sudo bash deploy.sh
#   # или
#   curl -fsSL https://raw.githubusercontent.com/.../deploy.sh | sudo bash -s --
#
# Откат:
#   sudo bash deploy.sh --rollback
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
    # Загружаем переменные из .env (игнорируем комментарии и пустые строки)
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Za-z_]+=.' "$ENV_FILE" 2>/dev/null || true)
    set +a
fi

# =============================================================================
# НАСТРАИВАЕМЫЕ ПАРАМЕТРЫ (приоритет: CLI > .env > defaults)
# =============================================================================

# Домен мессенджера (обязательно укажите ваш реальный домен)
DOMAIN="${MESSENGER_DOMAIN:-YOUR_DOMAIN_HERE}"

# Email для уведомлений Let's Encrypt
EMAIL="${MESSENGER_EMAIL:-YOUR_EMAIL_HERE}"

# Репозиторий мессенджера
REPO_URL="${MESSENGER_REPO:-https://github.com/your-org/messenger.git}"
REPO_BRANCH="${MESSENGER_BRANCH:-main}"

# Директории
INSTALL_DIR="/opt/messenger"
FRONTEND_DIR="/var/www/messenger"
LOG_DIR="/var/log/messenger"
DATA_DIR="/opt/messenger/data"

# Порты (8000 может быть занят VPN Manager, 3000 — Vite/React)
BACKEND_PORT=8001
FRONTEND_PORT=3001

# Системный пользователь
USER_NAME="messenger"
USER_GROUP="messenger"

# Python
PYTHON_VERSION="3.12"

# =============================================================================
# КОНСТАНТЫ
# =============================================================================

NGINX_CONF="/etc/nginx/sites-available/messenger"
NGINX_LINK="/etc/nginx/sites-enabled/messenger"
BACKEND_SERVICE="/etc/systemd/system/messenger-backend.service"
FRONTEND_SERVICE="/etc/systemd/system/messenger-frontend.service"
LOGROTATE_CONF="/etc/logrotate.d/messenger"
ENV_FILE="${INSTALL_DIR}/.env"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "Этот скрипт требует root или sudo прав. Запустите: sudo bash $0"
    fi
}

check_os() {
    if ! grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
        die "Этот скрипт поддерживает только Ubuntu. Текущая ОС: $(cat /etc/os-release 2>/dev/null | head -1)"
    fi

    local version
    version=$(lsb_release -rs 2>/dev/null || echo "0")
    if (( $(echo "$version < 20.04" | bc -l 2>/dev/null || echo 1) )); then
        die "Требуется Ubuntu 20.04 или новее. Текущая версия: $version"
    fi

    log_ok "ОС: Ubuntu $version"
}

check_nginx() {
    if ! command -v nginx &>/dev/null; then
        die "nginx не найден. Установите nginx перед запуском этого скрипта."
    fi
    log_ok "nginx: $(nginx -v 2>&1 | cut -d' ' -f3)"
}

check_domain() {
    if [ "$DOMAIN" = "messenger.example.com" ]; then
        die "Укажите реальный домен. Измените переменную DOMAIN в начале скрипта или задайте MESSENGER_DOMAIN."
    fi

    # Проверка DNS
    log_info "Проверка DNS для ${DOMAIN}..."
    local ip
    ip=$(dig +short "$DOMAIN" 2>/dev/null | head -1 || echo "")

    if [ -z "$ip" ]; then
        log_warn "Не удалось проверить DNS для ${DOMAIN}. Убедитесь что A-запись настроена."
    else
        local server_ip
        server_ip=$(curl -s ifconfig.me 2>/dev/null || echo "")
        if [ "$ip" != "$server_ip" ]; then
            log_warn "DNS ${DOMAIN} указывает на ${ip}, а сервер имеет IP ${server_ip}"
        else
            log_ok "DNS: ${DOMAIN} → ${ip}"
        fi
    fi

    log_ok "Домен: $DOMAIN"
}

# =============================================================================
# ОТКАТ
# =============================================================================

rollback() {
    log_warn "Начинаю откат..."

    # Остановка служб
    systemctl stop messenger-backend.service 2>/dev/null || true
    systemctl stop messenger-frontend.service 2>/dev/null || true

    # Удаление юнитов
    rm -f "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
    systemctl daemon-reload

    # Удаление nginx конфига
    rm -f "$NGINX_CONF" "$NGINX_LINK"
    nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

    # Удаление logrotate
    rm -f "$LOGROTATE_CONF"

    # Удаление пользователя
    userdel -r "$USER_NAME" 2>/dev/null || true

    # Удаление файлов
    rm -rf "$INSTALL_DIR" "$FRONTEND_DIR" "$LOG_DIR"

    log_ok "Откат завершён"
    exit 0
}

# =============================================================================
# ЭТАП 1: Проверки
# =============================================================================

step_checks() {
    log_info "=== Этап 1: Проверки ==="
    check_root
    check_os
    check_nginx
    check_domain
}

# =============================================================================
# ЭТАП 2: Установка зависимостей
# =============================================================================

step_dependencies() {
    log_info "=== Этап 2: Установка зависимостей ==="

    # Обновление пакетов
    apt-get update -qq

    # Python 3.12
    if ! command -v python${PYTHON_VERSION} &>/dev/null; then
        log_info "Установка Python ${PYTHON_VERSION}..."
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq
        apt-get install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev
    fi
    log_ok "Python: $(python${PYTHON_VERSION} --version)"

    # Node.js 20
    if ! command -v node &>/dev/null || [ "$(node -v | cut -d. -f1 | tr -d 'v')" -lt 18 ]; then
        log_info "Установка Node.js 20..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    fi
    log_ok "Node.js: $(node -v)"

    # Системные зависимости
    apt-get install -y --no-install-recommends \
        libmagic1 \
        git \
        certbot \
        python3-certbot-nginx \
        logrotate \
        build-essential

    # Poetry
    if ! command -v poetry &>/dev/null; then
        log_info "Установка Poetry..."
        curl -sSL https://install.python-poetry.org | python${PYTHON_VERSION} -
        ln -sf /root/.local/bin/poetry /usr/local/bin/poetry
    fi
    log_ok "Poetry: $(poetry --version)"

    # serve (для frontend)
    if ! command -v serve &>/dev/null; then
        log_info "Установка serve..."
        npm install -g serve
    fi
    log_ok "serve: $(serve --version 2>/dev/null || echo 'installed')"
}

# =============================================================================
# ЭТАП 3: Создание пользователя
# =============================================================================

step_user() {
    log_info "=== Этап 3: Создание пользователя ==="

    if id "$USER_NAME" &>/dev/null; then
        log_warn "Пользователь $USER_NAME уже существует"
    else
        useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" -m "$USER_NAME"
        log_ok "Создан пользователь: $USER_NAME"
    fi
}

# =============================================================================
# ЭТАП 4: Развёртывание backend
# =============================================================================

step_backend() {
    log_info "=== Этап 4: Развёртывание backend ==="

    # Клонирование или обновление
    if [ -d "${INSTALL_DIR}/.git" ]; then
        log_info "Обновление репозитория..."
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard "origin/${REPO_BRANCH}"
    else
        log_info "Клонирование репозитория..."
        rm -rf "$INSTALL_DIR"
        git clone -b "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"

    # Poetry install
    log_info "Установка Python зависимостей..."
    poetry config virtualenvs.create false
    poetry install --no-interaction --no-ansi --no-root

    # Создание директорий
    mkdir -p "$DATA_DIR/uploads" "$DATA_DIR/logs"
    chown -R "${USER_NAME}:${USER_GROUP}" "$INSTALL_DIR"
    chmod -R 750 "$INSTALL_DIR"
    chmod -R 755 "$DATA_DIR/uploads"

    # Создание .env
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Создание .env..."
        local jwt_secret
        jwt_secret=$(python${PYTHON_VERSION} -c "import secrets; print(secrets.token_urlsafe(32))")

        cat > "$ENV_FILE" <<EOF
# Messenger — Production Configuration
APP_NAME=Messenger
DEBUG=false
LOG_LEVEL=INFO

DATABASE_URL=sqlite+aiosqlite:///${DATA_DIR}/app.db

JWT_SECRET_KEY=${jwt_secret}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

UPLOAD_DIR=${DATA_DIR}/uploads
MAX_FILE_SIZE_MB=25

RATE_LIMIT_REQUESTS=5
RATE_LIMIT_SECONDS=1

CORS_ORIGINS=https://${DOMAIN}
EOF
        chown "${USER_NAME}:${USER_GROUP}" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        log_warn "JWT_SECRET_KEY сгенерирован. Сохраните его: ${ENV_FILE}"
    fi

    log_ok "Backend развёрнут: ${INSTALL_DIR}"
}

# =============================================================================
# ЭТАП 5: Сборка frontend
# =============================================================================

step_frontend() {
    log_info "=== Этап 5: Сборка frontend ==="

    cd "$INSTALL_DIR/frontend"

    # Install и build
    log_info "Установка npm зависимостей..."
    npm ci --production 2>/dev/null || npm install --production

    log_info "Сборка frontend..."
    npm run build

    # Копирование
    rm -rf "$FRONTEND_DIR"
    cp -r dist "$FRONTEND_DIR"
    chown -R "www-data:www-data" "$FRONTEND_DIR"
    chmod -R 755 "$FRONTEND_DIR"

    log_ok "Frontend собран: ${FRONTEND_DIR}"
}

# =============================================================================
# ЭТАП 6: systemd-юниты
# =============================================================================

step_systemd() {
    log_info "=== Этап 6: Настройка systemd ==="

    # Backend service
    cat > "$BACKEND_SERVICE" <<EOF
[Unit]
Description=Messenger Backend (FastAPI)
After=network.target
Wants=network.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_GROUP}
WorkingDirectory=${INSTALL_DIR}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python${PYTHON_VERSION} -m uvicorn messenger.main:app \\
    --host 127.0.0.1 \\
    --port ${BACKEND_PORT} \\
    --workers 2 \\
    --log-level info \\
    --access-log \\
    --log-config /dev/null
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/backend.log
StandardError=append:${LOG_DIR}/backend.log

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${DATA_DIR} ${LOG_DIR}
PrivateTmp=true

# Limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

    # Frontend service
    cat > "$FRONTEND_SERVICE" <<EOF
[Unit]
Description=Messenger Frontend (serve)
After=network.target
Wants=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${FRONTEND_DIR}
ExecStart=/usr/local/bin/serve \\
    --single \\
    --no-port-switching \\
    --no-clipboard \\
    --listen ${FRONTEND_PORT} \\
    --cors
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/frontend.log
StandardError=append:${LOG_DIR}/frontend.log

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${LOG_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    # Создание директории логов
    mkdir -p "$LOG_DIR"
    chown "${USER_NAME}:${USER_GROUP}" "$LOG_DIR"

    # Reload и enable
    systemctl daemon-reload
    systemctl enable messenger-backend.service
    systemctl enable messenger-frontend.service

    log_ok "systemd-юниты созданы"
}

# =============================================================================
# ЭТАП 7: Настройка nginx
# =============================================================================

step_nginx() {
    log_info "=== Этап 7: Настройка nginx ==="

    # Проверка что домен не занят
    if grep -q "server_name.*${DOMAIN}" /etc/nginx/sites-enabled/* 2>/dev/null; then
        die "Домен $DOMAIN уже используется в nginx. Измените DOMAIN или удалите существующую конфигурацию."
    fi

    cat > "$NGINX_CONF" <<EOF
# Upstream для backend
upstream messenger_backend {
    server 127.0.0.1:${BACKEND_PORT};
    keepalive 32;
}

# Upstream для frontend
upstream messenger_frontend {
    server 127.0.0.1:${FRONTEND_PORT};
    keepalive 32;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    # SSL сертификаты (будут обновлены certbot)
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Frontend (SPA)
    location / {
        proxy_pass http://messenger_frontend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://messenger_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Backend WebSocket
    location /ws {
        proxy_pass http://messenger_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket timeouts
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # Health check
    location /health {
        proxy_pass http://messenger_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }

    # Запрет доступа к скрытым файлам
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

    # Создание директории для certbot
    mkdir -p /var/www/certbot

    # Активация
    ln -sf "$NGINX_CONF" "$NGINX_LINK"

    # Тест и перезагрузка
    nginx -t || die "Ошибка конфигурации nginx"
    systemctl reload nginx

    log_ok "nginx настроен: ${NGINX_CONF}"
}

# =============================================================================
# ЭТАП 8: HTTPS (Let's Encrypt)
# =============================================================================

step_https() {
    log_info "=== Этап 8: Получение SSL сертификата ==="

    # Проверка что certbot установлен
    if ! command -v certbot &>/dev/null; then
        die "certbot не найден. Установите: apt-get install -y certbot python3-certbot-nginx"
    fi

    # Получение сертификата
    log_info "Запрос сертификата для ${DOMAIN}..."
    certbot --nginx \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        --redirect \
        --non-interactive \
        || log_warn "certbot не смог получить сертификат. Проверьте DNS и доступность домена."

    log_ok "HTTPS настроен"
}

# =============================================================================
# ЭТАП 9: Логирование и ротация
# =============================================================================

step_logrotate() {
    log_info "=== Этап 9: Настройка ротации логов ==="

    cat > "$LOGROTATE_CONF" <<EOF
${LOG_DIR}/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 ${USER_NAME} ${USER_GROUP}
    sharedscripts
    postrotate
        systemctl reload messenger-backend.service 2>/dev/null || true
        systemctl reload messenger-frontend.service 2>/dev/null || true
    endscript
}
EOF

    log_ok "logrotate настроен: ${LOGROTATE_CONF}"
}

# =============================================================================
# ЭТАП 10: Запуск служб
# =============================================================================

step_start() {
    log_info "=== Этап 10: Запуск служб ==="

    systemctl restart messenger-backend.service
    systemctl restart messenger-frontend.service

    # Ожидание запуска
    sleep 3

    # Проверка
    if systemctl is-active --quiet messenger-backend.service; then
        log_ok "Backend запущен (порт ${BACKEND_PORT})"
    else
        log_error "Backend не запустился. Проверьте: journalctl -u messenger-backend -n 50"
    fi

    if systemctl is-active --quiet messenger-frontend.service; then
        log_ok "Frontend запущен (порт ${FRONTEND_PORT})"
    else
        log_error "Frontend не запустился. Проверьте: journalctl -u messenger-frontend -n 50"
    fi
}

# =============================================================================
# ЭТАП 11: Финальная проверка
# =============================================================================

step_verify() {
    log_info "=== Этап 11: Финальная проверка ==="

    # Проверка backend
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log_ok "Backend отвечает: http://127.0.0.1:${BACKEND_PORT}/health"
    else
        log_error "Backend не отвечает (HTTP $http_code)"
    fi

    # Проверка frontend
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${FRONTEND_PORT}" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log_ok "Frontend отвечает: http://127.0.0.1:${FRONTEND_PORT}"
    else
        log_error "Frontend не отвечает (HTTP $http_code)"
    fi

    # Проверка nginx
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}/health" -k 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log_ok "nginx проксирует: https://${DOMAIN}/health"
    else
        log_warn "nginx не проксирует (HTTP $http_code). Возможно, сертификат ещё не получен."
    fi
}

# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

main() {
    echo ""
    echo "=============================================="
    echo "  Messenger — Развёртывание на VPS"
    echo "=============================================="
    echo ""
    echo "Домен:    ${DOMAIN}"
    echo "Email:    ${EMAIL}"
    echo "Backend:  ${INSTALL_DIR} (порт ${BACKEND_PORT})"
    echo "Frontend: ${FRONTEND_DIR} (порт ${FRONTEND_PORT})"
    echo ""

    # Обработка аргументов
    if [ "${1:-}" = "--rollback" ]; then
        rollback
    fi

    # Этапы
    step_checks
    step_dependencies
    step_user
    step_backend
    step_frontend
    step_systemd
    step_nginx
    step_https
    step_logrotate
    step_start
    step_verify

    echo ""
    echo "=============================================="
    echo "  Развёртывание завершено!"
    echo "=============================================="
    echo ""
    echo "  URL:        https://${DOMAIN}"
    echo "  Backend:    http://127.0.0.1:${BACKEND_PORT}"
    echo "  Frontend:   http://127.0.0.1:${FRONTEND_PORT}"
    echo "  Логи:       ${LOG_DIR}/"
    echo "  Бэкап:      make backup (в ${INSTALL_DIR})"
    echo ""
    echo "  Команды:"
    echo "    systemctl status messenger-backend"
    echo "    systemctl status messenger-frontend"
    echo "    journalctl -u messenger-backend -f"
    echo "    nginx -t && systemctl reload nginx"
    echo ""
    echo "  Откат: sudo bash $0 --rollback"
    echo ""
}

main "$@"
