# 🚀 Развёртывание

## Требования к окружению

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| CPU | 1 ядро | 2 ядра |
| RAM | 512 МБ | 1 ГБ |
| Диск | 5 ГБ | 10 ГБ |
| ОС | Linux x86_64 | Ubuntu 22.04+ |
| Docker | 24.0+ | Последняя |
| Docker Compose | 2.20+ | Последняя |

## Переменные окружения

| Переменная | Тип | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `APP_NAME` | string | Messenger | Название приложения |
| `DEBUG` | bool | false | Режим отладки |
| `LOG_LEVEL` | string | INFO | Уровень логирования |
| `DATABASE_URL` | string | sqlite+aiosqlite:///./data/app.db | URL БД |
| `JWT_SECRET_KEY` | string | **Обязательно** | Секретный ключ JWT |
| `JWT_ALGORITHM` | string | HS256 | Алгоритм JWT |
| `JWT_EXPIRE_MINUTES` | int | 10080 | Время жизни токена (7 дней) |
| `UPLOAD_DIR` | string | ./data/uploads | Директория файлов |
| `MAX_FILE_SIZE_MB` | int | 25 | Макс. размер файла |
| `RATE_LIMIT_REQUESTS` | int | 5 | Запросов в секунду |
| `CORS_ORIGINS` | string | http://localhost,... | CORS origins (через запятую) |

## Быстрый старт

### 1. Клонирование

```bash
git clone <repo-url>
cd messenger
```

### 2. Настройка

```bash
cp .env.example .env
# Отредактируйте .env:
# - JWT_SECRET_KEY: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# - CORS_ORIGINS: добавьте ваш IP/домен
```

### 3. Запуск

```bash
make build    # Сборка без кеша
make up       # Запуск
```

### 4. Проверка

```bash
make logs     # Логи приложения
curl http://localhost:8000/health  # Health check
```

## Docker Compose

### Сервисы

| Сервис | Образ | Порты | Описание |
|--------|-------|-------|----------|
| app | Custom | 8000 | Backend (FastAPI) |
| frontend | nginx:alpine | 9000:80 | Frontend (Vue 3 PWA) |
| proxy | caddy:2-alpine | 80, 443 | Reverse proxy + HTTPS |

### Сети

- `ms-net` — внутренняя сеть для коммуникации

### Тома

- `./data` — БД, логи, uploads
- `caddy-data` — данные Caddy
- `caddy-config` — конфиг Caddy

## Production

### Домен и DNS

1. Купите домен
2. Направьте A-запись на IP сервера
3. Обновите `Caddyfile`: замените `your-domain.com`
4. Обновите `.env`: `CORS_ORIGINS=http://your-domain.com`

### HTTPS

Caddy автоматически получает и обновляет SSL-сертификаты Let's Encrypt.

### Бэкапы

```bash
make backup    # Создать бэкап
make restore BACKUP_FILE=./backups/app_2024-01-01.db.gz  # Восстановить
```

### Cron автобэкапов

```bash
# /etc/crontab
0 2 * * * /path/to/scripts/cron-backup.sh
```

## Локальная разработка

### Backend

```bash
poetry install
uvicorn messenger.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Тесты

```bash
make test       # Запуск тестов
make test-cov   # С coverage
make lint       # Линтинг
make format     # Форматирование
```

## Troubleshooting

### CORS ошибки

Проверьте `CORS_ORIGINS` в `.env` — должен содержать ваш домен/IP.

### JWT ошибки

Убедитесь что `JWT_SECRET_KEY` установлен и не пустой.

### Permission denied

Проверьте права на `./data` — должен быть доступен контейнеру.

### Порт занят

Измените маппинг в `docker-compose.yml`:
```yaml
frontend:
  ports:
    - "9001:80"  # вместо 9000
```
