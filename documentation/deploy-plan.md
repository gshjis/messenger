# 📋 План развёртывания мессенджера на VPS (Ubuntu + systemd + nginx)

## Обзор

Развёртывание без Docker — нативная установка на Ubuntu с systemd-юнитами и nginx в качестве reverse proxy.

## Архитектура

```
                    ┌─────────────────────────────────────────┐
                    │              VPS (Ubuntu)                │
                    │                                         │
  Internet ────────►│  nginx :443 (HTTPS, Let's Encrypt)      │
                    │    │                                    │
                    │    ├─ /messenger/      → frontend :3001       │
                    │    ├─ /messenger/api/* → backend  :8001       │
                    │    └─ /messenger/ws    → backend  :8001 (WS)  │
                    │                                         │
                    │  ┌─────────────┐  ┌──────────────────┐  │
                    │  │ systemd:    │  │ systemd:         │  │
                    │  │ messenger-  │  │ messenger-       │  │
                    │  │ frontend    │  │ backend          │  │
                    │  │(serve :3001)│  │ (uvicorn :8001)  │  │
                    │  └─────────────┘  └──────────────────┘  │
                    │                                         │
                    │  ┌─────────────┐  ┌──────────────────┐  │
                    │  │ /var/www/   │  │ /opt/messenger/  │  │
                    │  │ messenger/  │  │ (backend code)   │  │
                    │  │ (dist)      │  │ /data/ (SQLite)  │  │
                    │  └─────────────┘  └──────────────────┘  │
                    │                                         │
                    │  VPN: не затрагивается                  │
                    └─────────────────────────────────────────┘
```

## Этапы установки

### 1. Подготовка

- Проверка ОС (Ubuntu 20.04+)
- Проверка root/sudo
- Проверка что nginx установлен
- Проверка что домен настроен (A-запись)

### 2. Установка зависимостей

- Python 3.12 (deadsnakes PPA)
- Node.js 20 (NodeSource)
- Poetry, certbot, logrotate

### 3. Развёртывание backend

- Клонирование репозитория в `/opt/messenger`
- `poetry install --no-dev`
- Создание `.env`
- Создание пользователя `messenger`

### 4. Сборка frontend

- `npm install && npm run build`
- Копирование `dist/` в `/var/www/messenger`

### 5. systemd-юниты

- `messenger-backend.service` — uvicorn на порту 8000
- `messenger-frontend.service` — serve на порту 3000
- Auto-restart, logging, limits

### 6. Настройка nginx

- Server block для домена
- Reverse proxy: `/` → `http://127.0.0.1:3000`
- Reverse proxy: `/api/` → `http://127.0.0.1:8000`
- Reverse proxy: `/ws` → `http://127.0.0.1:8000` (WebSocket upgrade)
- HTTPS через Let's Encrypt (certbot)

### 7. Логирование и ротация

- Backend: `/var/log/messenger/backend.log`
- Frontend: `/var/log/messenger/frontend.log`
- logrotate: ежедневная ротация, 30 дней хранение

### 8. Безопасность

- Пользователь `messenger` без shell
- Права на `/opt/messenger` — 750
- Права на `/var/www/messenger` — 755
- UFW: только 80, 443

## Структура файлов после установки

```
/opt/messenger/              # Backend код
├── messenger/               # Python пакеты
├── .env                     # Переменные окружения
├── pyproject.toml
├── poetry.lock
├── data/                    # SQLite БД, логи, uploads
│   ├── app.db
│   ├── uploads/
│   └── logs/
└── scripts/                 # Бэкапы

/var/www/messenger/          # Frontend статика
├── index.html
├── assets/
└── ...

/etc/systemd/system/
├── messenger-backend.service
└── messenger-frontend.service

/etc/nginx/sites-available/messenger
/etc/nginx/sites-enabled/messenger

/etc/logrotate.d/messenger

/var/log/messenger/
├── backend.log
└── frontend.log
```

## Схема маршрутизации nginx

```
https://messenger.example.com/
    ↓
nginx (443, HTTPS)
    ├─ /          → http://127.0.0.1:3000/  (frontend SPA)
    ├─ /api/*     → http://127.0.0.1:8000/api/*  (backend REST)
    └─ /ws        → http://127.0.0.1:8000/ws  (backend WebSocket)
         Upgrade: websocket
         Connection: upgrade
```

## Настраиваемые параметры

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `DOMAIN` | messenger.example.com | Домен мессенджера |
| `EMAIL` | admin@example.com | Email для Let's Encrypt |
| `INSTALL_DIR` | /opt/messenger | Директория backend |
| `FRONTEND_DIR` | /var/www/messenger | Директория frontend |
| `BACKEND_PORT` | 8000 | Порт backend |
| `FRONTEND_PORT` | 3000 | Порт frontend |
| `USER_NAME` | messenger | Системный пользователь |
| `LOG_DIR` | /var/log/messenger | Директория логов |
