# 📨 Личный мессенджер

Self-hosted мессенджер для личного использования. Python + FastAPI + Vue 3 PWA.

## Возможности (MVP)

- ✅ Авторизация по invite-коду
- ✅ Личные и групповые чаты (до 20 чел)
- ✅ Текст, эмодзи, фото, документы (до 25 МБ)
- ✅ Статусы: отправлено → доставлено → прочитано
- ✅ Real-time через WebSocket
- ✅ Поиск по сообщениям
- ✅ PWA (установка на телефон)
- ✅ Тёмная/светлая тема
- ✅ Админка (удаление, бан, очистка)

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.12 + FastAPI |
| ORM/БД | SQLModel + SQLite (WAL режим) |
| Real-time | FastAPI WebSockets |
| Auth | JWT (HttpOnly cookie) + argon2id |
| Файлы | python-magic (MIME проверка) |
| Frontend | Vue 3 + Vite + PWA |
| Прокси | Caddy (авто-HTTPS) |

## Быстрый старт

### 1. Клонирование

```bash
git clone <repo-url>
cd messenger
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env — обязательно смените JWT_SECRET_KEY!
```

### 3. Запуск

```bash
make up
```

### 4. Открыть браузер

```
http://localhost
```

## Git hooks

### Запуск тестов при слиянии в main

```bash
# Установка post-merge hook
cp hooks/post-merge .git/hooks/post-merge
chmod +x .git/hooks/post-merge
```

После этого при каждом `git merge` в ветку `main` автоматически запустятся тесты.
Если тесты провалятся — merge будет отменён.

## Команды Makefile

| Команда | Описание |
|---------|----------|
| `make up` | Запуск всех сервисов |
| `make down` | Остановка |
| `make restart` | Перезапуск |
| `make logs` | Логи приложения |
| `make backup` | Бэкап БД |
| `make restore BACKUP_FILE=path` | Восстановление из бэкапа |
| `make test` | Запуск тестов |
| `make test-cov` | Тесты с coverage |
| `make lint` | Линтинг |
| `make format` | Форматирование кода |
| `make clean` | Очистка кеша |

## Структура проекта

```
messenger/
├── messenger/
│   ├── __init__.py
│   ├── main.py              # Точка входа FastAPI
│   ├── config.py             # Настройки (pydantic-settings)
│   ├── database.py           # SQLite + WAL
│   ├── models/               # SQLModel модели
│   │   ├── user.py
│   │   ├── chat.py
│   │   ├── chat_member.py
│   │   ├── message.py
│   │   └── invite_code.py
│   ├── schemas/              # Pydantic схемы
│   ├── api/                  # REST роутеры
│   │   ├── auth.py
│   │   ├── chat.py
│   │   └── files.py
│   ├── websockets/           # WebSocket handlers
│   │   ├── manager.py
│   │   └── handler.py
│   ├── security/             # Auth, JWT, argon2
│   └── utils/                # Утилиты
├── frontend/                 # Vue 3 PWA
├── tests/                    # Тесты
├── Dockerfile
├── docker-compose.yml
├── Caddyfile
├── nginx.conf
├── Makefile
└── .env.example
```

## Безопасность

- HTTPS через Caddy (авто Let's Encrypt)
- JWT в HttpOnly cookie
- Пароли: argon2id
- Файлы: проверка MIME через python-magic, лимит 25 МБ
- Rate limiting: 5 запросов/сек на IP
- Данные хранятся только на вашем сервере

## Бэкапы

```bash
# Создать бэкап
make backup

# Восстановить
make restore BACKUP_FILE=./backups/app_2024-01-01.db
```

Бэкапы хранятся в `./backups/`. Рекомендуется настроить cron для автоматических бэкапов.

## Установка на телефон (PWA)

### Android (Chrome)
1. Откройте мессенджер в Chrome
2. Нажмите "⋮" → "Установить приложение"
3. Или: Настройки → "Добавить на главный экран"

### iOS (Safari)
1. Откройте мессенджер в Safari
2. Нажмите "Поделиться" → "На экран «Домой»"
3. Подтвердите установку

> **Примечание:** Push-уведомления на iOS ограничены для PWA. На Android работают стабильнее.

## Развёртывание на VPS

1. Купите домен и направьте A-запись на IP сервера
2. Установите Docker + Docker Compose
3. Скопируйте проект на сервер
4. В `.env` укажите `MESSENGER_DOMAIN=your-domain.com`
5. В `Caddyfile` замените `your-domain.com` на ваш домен
6. Запустите: `make up`

Caddy автоматически получит и обновит SSL-сертификат Let's Encrypt.

## Лицензия

MIT
