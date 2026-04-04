# 🌐 Настройка хостового nginx

## Обзор

Настройка nginx на хосте (не в Docker) для проксирования запросов к мессенджеру.

## Предварительные требования

- nginx установлен и работает
- Домен настроен (A-запись на IP сервера)
- SSL сертификат (Let's Encrypt или другой)

## Интеграция с существующим конфигом VPN Manager

Объедините оба сервиса в одном `server` блоке:

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name gshjis.org;

    # SSL сертификаты
    ssl_certificate     /etc/letsencrypt/live/gshjis.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gshjis.org/privkey.pem;

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

    # ===== VPN Manager =====
    location /vpn/ {
        alias /var/www/vpn-manager/;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /vpn/api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ===== Мессенджер =====

    # Frontend SPA
    location /messenger/ {
        proxy_pass http://127.0.0.1:3001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /messenger/api/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Backend WebSocket
    location /messenger/ws {
        proxy_pass http://127.0.0.1:8001/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # Health check
    location /messenger/health {
        proxy_pass http://127.0.0.1:8001/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Запрет доступа к скрытым файлам
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

## Активация

```bash
# Тест конфигурации
sudo nginx -t

# Перезагрузка nginx
sudo systemctl reload nginx
```

## Запуск мессенджера

### Backend (порт 8001)

```bash
cd /opt/messenger
poetry install
uvicorn messenger.main:app --host 127.0.0.1 --port 8001 --workers 2
```

### Frontend (порт 3001)

```bash
cd /opt/messenger/frontend
npm install
npm run build
npx serve --single --listen 3001 --cors dist/
```

## Проверка

```bash
# Health check
curl https://gshjis.org/messenger/health

# Frontend
curl https://gshjis.org/messenger/

# API
curl https://gshjis.org/messenger/api/auth/login
```

## Troubleshooting

### 502 Bad Gateway

- Проверьте что backend запущен: `curl http://127.0.0.1:8001/health`
- Проверьте что frontend запущен: `curl http://127.0.0.1:3001/`

### WebSocket не работает

- Убедитесь что `Upgrade` и `Connection` заголовки передаются
- Проверьте что `proxy_read_timeout` достаточно большой (7d)

### SSL ошибки

- Проверьте путь к сертификатам
- Обновите сертификаты: `sudo certbot renew`
