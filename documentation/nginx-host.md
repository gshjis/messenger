# 🌐 Настройка хостового nginx

## Обзор

Настройка nginx на хосте (не в Docker) для проксирования запросов к мессенджеру.

## Предварительные требования

- nginx установлен и работает
- Домен настроен (A-запись на IP сервера)
- SSL сертификат (Let's Encrypt или другой)

## Конфигурация nginx

Создайте файл `/etc/nginx/sites-available/messenger`:

```nginx
# Upstream для backend мессенджера
upstream messenger_backend {
    server 127.0.0.1:8001;
    keepalive 32;
}

# Upstream для frontend мессенджера
upstream messenger_frontend {
    server 127.0.0.1:3001;
    keepalive 32;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name messenger.example.com;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name messenger.example.com;

    # SSL сертификаты
    ssl_certificate     /etc/letsencrypt/live/messenger.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/messenger.example.com/privkey.pem;

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

    # Мессенджер — location для добавления в существующий server block
    # Frontend SPA
    location /messenger/ {
        proxy_pass http://messenger_frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /messenger/api/ {
        proxy_pass http://messenger_backend;
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
        proxy_pass http://messenger_backend;
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
        proxy_pass http://messenger_backend;
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
# Создание symlink
sudo ln -s /etc/nginx/sites-available/messenger /etc/nginx/sites-enabled/

# Тест конфигурации
sudo nginx -t

# Перезагрузка nginx
sudo systemctl reload nginx
```

## Запуск мессенджера

### Backend

```bash
cd /opt/messenger
poetry install
uvicorn messenger.main:app --host 127.0.0.1 --port 8001 --workers 2
```

### Frontend

```bash
cd /opt/messenger/frontend
npm install
npm run build
npx serve --single --listen 3001 --cors dist/
```

## Проверка

```bash
# Health check
curl https://messenger.example.com/messenger/health

# Frontend
curl https://messenger.example.com/messenger/

# API
curl https://messenger.example.com/messenger/api/auth/login
```

## Интеграция с существующим nginx

Если у вас уже есть server block для домена, добавьте location блоки в него:

```nginx
server {
    # ... существующая конфигурация ...

    # Мессенджер
    location /messenger/ {
        proxy_pass http://messenger_frontend;
        # ... настройки прокси ...
    }

    location /messenger/api/ {
        proxy_pass http://messenger_backend;
        # ... настройки прокси ...
    }

    location /messenger/ws {
        proxy_pass http://messenger_backend;
        # ... настройки WebSocket ...
    }
}
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
