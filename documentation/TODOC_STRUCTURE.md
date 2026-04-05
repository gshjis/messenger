# 📘 Техническая документация — Личный мессенджер

> Self-hosted мессенджер для личного использования. Python + FastAPI + Vue 3 PWA.

---

## Оглавление

### 1. Введение
- **1.1. Назначение документа** — Целевая аудитория, область применения, как пользоваться документацией
- **1.2. Обзор проекта** — Краткое описание мессенджера, основные возможности (MVP)
- **1.3. Технологический стек** — Таблица технологий с версиями и обоснованием выбора
- **1.4. Термины и сокращения** — Глоссарий (JWT, PWA, WAL, MIME, CORS, WebSocket и т.д.)

### 2. Архитектура системы
- **2.1. Общая архитектура** — High-level обзор компонентов, схема взаимодействия
  - *Mermaid-диаграмма: Component Diagram (Frontend ↔ Nginx ↔ Backend ↔ SQLite)*
- **2.2. Архитектурные решения** — Двухзвенная архитектура (frontend + backend), почему не микросервисы, trade-offs
- **2.3. Структура проекта** — Дерево файлов и директорий с описанием назначения каждого
- **2.4. Поток данных** — Sequence Diagram основных сценариев
  - *Mermaid-диаграмма: Sequence Diagram (регистрация, логин, отправка сообщения)*
- **2.5. Масштабируемость и ограничения** — Лимиты (20 чел в чате, 25 МБ файлы), горизонты масштабирования

### 3. Настройка окружения
- **3.1. Системные требования** — Минимальные и рекомендуемые требования к серверу
- **3.2. Установка зависимостей** — Docker, Docker Compose, Node.js (для разработки)
- **3.3. Клонирование репозитория** — Пошаговая инструкция
- **3.4. Конфигурация .env** — Подробное описание каждой переменной окружения
  - Таблица: Переменная | Тип | По умолчанию | Описание | Обязательно
- **3.5. Генерация секретов** — Команды для генерации JWT_SECRET_KEY, invite-кодов
- **3.6. Локальный запуск (разработка)** — `make up`, hot-reload, проксирование
- **3.7. Production развёртывание** — VPS, домен, DNS, `scripts/deploy.sh`
- **3.8. Troubleshooting окружения** — Частые проблемы и решения

### 4. База данных
- **4.1. Обзор БД** — SQLite, почему выбран, преимущества и ограничения
- **4.2. WAL режим** — Что такое Write-Ahead Logging, почему включён, PRAGMA настройки
  - `PRAGMA journal_mode=WAL`
  - `PRAGMA synchronous=NORMAL`
  - `PRAGMA foreign_keys=ON`
- **4.3. Схема данных** — ER-диаграмма всех таблиц
  - *Mermaid-диаграмма: ER Diagram (users, chats, chat_members, messages, invite_codes)*
- **4.4. Модели данных (SQLModel)**
  - **4.4.1. User** — Поля, индексы, ограничения
  - **4.4.2. Chat** — Типы чатов (personal/group), поля
  - **4.4.3. ChatMember** — Роли (admin/member), связи
  - **4.4.4. Message** — Статусы, файлы, soft-delete
  - **4.4.5. InviteCode** — Логика использования, expiration
- **4.5. Инициализация БД** — Процесс создания таблиц, [`init_db()`](messenger/database.py:34)
- **4.6. Сессии и транзакции** — [`get_session()`](messenger/database.py:51), rollback, connection pooling
- **4.7. Миграции** — Alembic интеграция, процесс миграции схемы
- **4.8. Производительность** — Индексы, оптимизация запросов, лимиты SQLite

### 5. Бэкенд (FastAPI)
- **5.1. Точка входа** — [`main.py`](messenger/main.py), инициализация приложения, lifespan
- **5.2. Конфигурация** — [`config.py`](messenger/config.py), pydantic-settings, валидация
- **5.3. Middleware**
  - **5.3.1. CORS** — Настройка, разрешённые origins
  - **5.3.2. Security Headers** — X-Content-Type-Options, X-Frame-Options, HSTS и др.
  - **5.3.3. Rate Limiting** — SlowAPI, настройки, обработка 429
- **5.4. Логирование** — Loguru, ротация, уровни, формат
- **5.5. Health Check** — Endpoint `/health`, мониторинг
- **5.6. Dependency Injection** — Паттерн FastAPI, переопределение в тестах

### 6. API-контракты
- **6.1. Обзор API** — Базовый URL, префиксы, версионирование
- **6.2. Аутентификация** (`/api/auth`)
  - `POST /api/auth/login` — Логин, request/response, cookie
  - `POST /api/auth/register` — Регистрация по invite-коду
  - `GET /api/auth/me` — Данные текущего пользователя
  - `PUT /api/auth/me` — Обновление профиля
  - `POST /api/auth/invite` — Генерация invite-кода
  - `POST /api/auth/logout` — Выход
- **6.3. Пользователи** (`/api/users`)
  - `GET /api/users/search` — Поиск пользователей по username
- **6.4. Чаты** (`/api/chats`)
  - `POST /api/chats` — Создание чата
  - `GET /api/chats` — Список чатов пользователя
  - `GET /api/chats/{id}` — Информация о чате
  - `DELETE /api/chats/{id}` — Удаление чата
  - `GET /api/chats/{id}/members` — Список участников
  - `POST /api/chats/{id}/members` — Добавление участника
  - `DELETE /api/chats/{id}/members/{user_id}` — Удаление участника
  - `PUT /api/chats/{id}/members/{user_id}/role` — Смена роли
- **6.5. Сообщения**
  - `POST /api/chats/{id}/messages` — Отправка
  - `GET /api/chats/{id}/messages` — Список с пагинацией
  - `GET /api/chats/{id}/messages/search` — Поиск
  - `DELETE /api/chats/{id}/messages/{id}` — Удаление (soft-delete)
- **6.6. Файлы** (`/api/files`)
  - `POST /api/files/{chat_id}/upload` — Загрузка
  - `GET /api/files/{chat_id}/{file_path}` — Скачивание
- **6.7. WebSocket** (`/ws`)
  - Протокол подключения, аутентификация через query param
  - Actions: `subscribe`, `unsubscribe`, `message`, `mark_read`, `ping`
  - Формат сообщений (JSON schema)
- **6.8. Коды ошибок** — Таблица HTTP статусов и их значений
- **6.9. Pydantic схемы** — Полные описания request/response моделей

### 7. Бизнес-логика
- **7.1. Система аутентификации**
  - Flow регистрации по invite-коду
  - JWT token lifecycle (создание, валидация, expiration)
  - HttpOnly cookie vs Authorization header
  - [`get_current_user()`](messenger/api/auth.py:31) dependency
- **7.2. Invite-коды**
  - Генерация, валидация, подсчёт использований
  - Ограничения (max_uses, expires_at, is_active)
  - Админ-код для первого входа
- **7.3. Управление чатами**
  - Создание личного и группового чата
  - Роли участников (admin/member) и права
  - Удаление чата (каскадное удаление сообщений и участников)
- **7.4. Сообщения**
  - Статусы: sent → delivered → read
  - Soft-delete (is_deleted flag)
  - Поиск с экранированием LIKE-спецсимволов
  - Пагинация (page/per_page, has_next)
- **7.5. Файловая система**
  - Загрузка: проверка размера, MIME через python-magic
  - Разрешённые типы файлов (таблица)
  - Хранение: UUID-имена, структура директорий
  - Защита от path traversal
  - Soft-link на сообщения

### 8. Безопасность и шифрование
- **8.1. Обзор угроз** — Threat model для self-hosted мессенджера
- **8.2. JWT (JSON Web Tokens)**
  - Алгоритм HS256, структура payload
  - [`create_access_token()`](messenger/security/auth.py:28) / [`decode_access_token()`](messenger/security/auth.py:41)
  - Хранение: HttpOnly + Secure + SameSite=Lax cookies
  - Срок жизни (7 дней по умолчанию)
- **8.3. Хеширование паролей**
  - Argon2id — почему выбран, параметры
  - [`hash_password()`](messenger/security/auth.py:15) / [`verify_password()`](messenger/security/auth.py:20)
- **8.4. Rate Limiting**
  - SlowAPI, 5 запросов/сек на IP
  - Обработка превышения (429)
- **8.5. Security Headers**
  - Полный список headers с описанием
  - HSTS, X-Frame-Options, CSP (если применимо)
- **8.6. CORS** — Настройка, разрешённые origins, credentials
- **8.7. Защита файлов**
  - MIME validation через python-magic
  - Path traversal prevention
  - UUID-имена файлов
- **8.8. Invite-коды как механизм контроля доступа**
- **8.9. Чек-лист безопасности** — Production checklist

### 9. Real-time коммуникация (WebSocket)
- **9.1. Архитектура WebSocket** — [`ConnectionManager`](messenger/websockets/manager.py:9)
- **9.2. Протокол подключения**
  - Аутентификация через token query param
  - Коды закрытия (4001, 4002, 4003)
- **9.3. Управление подписками**
  - `subscribe` / `unsubscribe` на чаты
  - Структура данных: `_active_connections`, `_chat_subscriptions`, `_user_subscriptions`
- **9.4. Рассылка сообщений**
  - [`broadcast_to_chat()`](messenger/websockets/manager.py:78) — fan-out с исключением отправителя
  - [`send_personal_message()`](messenger/websockets/manager.py:66) — персональные уведомления
- **9.5. Обработчики действий**
  - `message` — сохранение в БД + broadcast
  - `mark_read` — обновление статусов + уведомления отправителям
  - `ping/pong` — keepalive
- **9.6. Reconnection** — Стратегия повторного подключения на клиенте (3 сек)
- **9.7. Масштабируемость** — Ограничения in-memory менеджера, пути к горизонтальному масштабированию (Redis Pub/Sub)

### 10. Фронтенд (Vue 3 PWA)
- **10.1. Обзор** — Vue 3 Composition API, Vite, Pinia, PWA
- **10.2. Структура проекта** — Дерево файлов frontend/
- **10.3. Роутинг**
  - [`router.js`](frontend/src/router.js) — маршруты, guards (requiresAuth, guest)
  - Base path: `/messenger/`
- **10.4. State Management (Pinia)**
  - **10.4.1. Auth Store** — [`auth.js`](frontend/src/stores/auth.js): login, register, fetchMe, logout, generateInvite
  - **10.4.2. Chat Store** — [`chat.js`](frontend/src/stores/chat.js): fetchChats, selectChat, sendMessage, pagination
- **10.5. Компоненты**
  - **10.5.1. App.vue** — Корневой компонент, инициализация
  - **10.5.2. AuthView.vue** — Формы логина/регистрации
  - **10.5.3. ChatView.vue** — Основной интерфейс чата, sidebar, модальные окна
- **10.6. WebSocket клиент**
  - Подключение, подписка на чаты
  - Обработка `new_message`, reconnection
- **10.7. PWA**
  - Manifest, service worker (vite-plugin-pwa)
  - Установка на Android/iOS
  - Ограничения push-уведомлений на iOS
- **10.8. Темы** — Тёмная/светлая тема, CSS variables, `data-theme` атрибут
- **10.9. Сборка и деплой** — Vite build, nginx, base path
- **10.10. Статус реализации фронтенда**
  - **10.10.1. Таблица соответствия API endpoints** — Какие endpoints бэкенда реализованы во фронтенде, какие нет
    - Таблица: Endpoint | Реализован | Файл | Примечание
  - **10.10.2. Реализованный функционал** — Auth, список чатов, отправка сообщений, WebSocket, поиск пользователей
  - **10.10.3. Нереализованный функционал** — Удаление чатов/сообщений, управление участниками, файлы, админка
  - **10.10.4. План развития фронтенда** — Приоритеты для будущих итераций

### 11. Docker и контейнеризация
- **11.1. Backend Dockerfile** — Multi-stage build (deps → runtime), non-root user
- **11.2. Frontend Dockerfile** — Multi-stage build (node → nginx:alpine)
- **11.3. Docker Compose** — [`docker-compose.yml`](docker-compose.yml): сервисы, сети, volumes
- **11.4. Resource Limits** — CPU: 1.0, Memory: 512M
- **11.5. Health Checks** — `/health` endpoint, interval, retries
- **11.6. Сетевая архитектура** — ms-net bridge, port mapping (127.0.0.1:8001, 9000)
- **11.7. .dockerignore** — Что исключается из образов

### 12. Nginx и проксирование
- **12.1. Frontend Nginx** — [`nginx.conf`](frontend/nginx.conf): SPA fallback, gzip, cache
- **12.2. Production Nginx** — Location blocks для `/messenger/`, `/messenger/api/`, `/messenger/ws`
- **12.3. WebSocket проксирование** — Upgrade header, timeout 7d
- **12.4. Upstream конфигурация** — keepalive 32
- **12.5. SSL/TLS** — Certbot, Let's Encrypt, автообновление

### 13. Процесс деплоя
- **13.1. Обзор** — Архитектура деплоя (Docker Compose + хостовой nginx)
- **13.2. Скрипт deploy.sh** — Поэтапное описание:
  - Этап 1: Проверки (Docker, nginx, root)
  - Этап 2: Настройка .env (генерация JWT secret)
  - Этап 3: Сборка и запуск контейнеров
  - Этап 4: Настройка nginx location
  - Этап 5: Логирование
  - Этап 6: SSL сертификат (certbot)
  - Этап 7: Инициализация (первый invite-код)
- **13.3. Откат** — `--rollback` флаг, что делает
- **13.4. Makefile команды** — Таблица всех команд
- **13.5. Обновление приложения** — `git pull` + `make restart`, post-merge hook
- **13.6. VPS deployment guide** — Пошаговая инструкция от нуля до working product

### 14. Бэкапы и восстановление
- **14.1. Стратегия бэкапов** — Частота, хранение, ротация (30 дней)
- **14.2. Скрипт backup.sh** — sqlite3 .backup, gzip, fallback
- **14.3. Скрипт restore.sh** — Пошаговое восстановление
- **14.4. Makefile команды** — `make backup`, `make restore`
- **14.5. Автоматические бэкапы** — [`cron-backup.sh`](scripts/cron-backup.sh), crontab
- **14.6. Проверка целостности** — sqlite3 integrity check

### 15. CI/CD и качество кода
- **15.1. Pre-commit hooks** — [`.pre-commit-config.yaml`](.pre-commit-config.yaml): ruff, mypy
- **15.2. Линтинг** — Ruff правила, автофикс
- **15.3. Типизация** — MyPy настройки, strict mode
- **15.4. Форматирование** — Ruff format, line-length 120
- **15.5. Git hooks** — [`post-merge`](hooks/post-merge): автотесты при merge в main
- **15.6. CI/CD Pipeline** — Рекомендуемая конфигурация (GitHub Actions example)

### 16. Тестирование
- **16.1. Обзор** — pytest, pytest-asyncio, httpx ASGI transport
- **16.2. Фикстуры** — [`conftest.py`](tests/conftest.py): test_session, client, auth_client, test_user
- **16.3. Тестовая БД** — In-memory SQLite, StaticPool, очистка таблиц
- **16.4. Тесты аутентификации** — [`test_auth.py`](tests/test_auth.py): login, register, me, profile, invite, logout
- **16.5. Тесты чатов** — [`test_chat_api.py`](tests/test_chat_api.py): CRUD, members, messages
- **16.6. Тесты безопасности** — [`test_security.py`](tests/test_security.py): password hashing, JWT
- **16.7. Тесты моделей** — [`test_models.py`](tests/test_models.py): SQLModel validation
- **16.8. Health check тесты** — [`test_health.py`](tests/test_health.py)
- **16.9. Coverage** — Требования (80%+), отчёты
- **16.10. Запуск тестов** — `make test`, `make test-cov`

### 17. Мониторинг и логирование
- **17.1. Логирование приложения** — Loguru, уровни, формат, ротация
- **17.2. Логи в файл** — `data/logs/messenger_YYYY-MM-DD.log`, 30 дней retention
- **17.3. Docker логи** — `docker compose logs -f app`
- **17.4. Health Check мониторинг** — `/health` endpoint, Docker healthcheck
- **17.5. Рекомендуемый мониторинг** — Uptime Kuma, Prometheus + Grafana (опционально)
- **17.6. Алертинг** — Email уведомления, webhook интеграции

### 18. Руководство по устранению проблем (Troubleshooting)
- **18.1. Диагностика** — Пошаговый подход к поиску проблем
- **18.2. Частые проблемы**
  - Backend не запускается
  - WebSocket не подключается
  - Файлы не загружаются
  - JWT token не работает
  - База данных повреждена
  - Nginx 502 Bad Gateway
  - CORS ошибки
- **18.3. Логи** — Где искать, как читать
- **18.4. Docker** — `docker compose ps`, `docker compose logs`, restart
- **18.5. База данных** — sqlite3 CLI, integrity check, восстановление
- **18.6. Сеть** — curl тесты, port checking, firewall
- **18.7. FAQ** — Часто задаваемые вопросы

### 19. Приложение
- **A. Полная схема БД** — SQL CREATE statements
- **B. Полные API спецификации** — OpenAPI/Swagger export
- **C. WebSocket протокол** — Полная спецификация сообщений
- **D. Переменные окружения** — Полная таблица с примерами
- **E. Чек-лист production readiness**
- **F. Ссылки на документацию зависимостей**
- **G. Лицензия (MIT)**

---

## Рекомендуемые Mermaid-диаграммы

1. **Component Diagram** — Общая архитектура (Раздел 2.1)
2. **Sequence Diagram: Регистрация** — Flow от invite-кода до JWT (Раздел 2.4)
3. **Sequence Diagram: Отправка сообщения** — REST + WebSocket broadcast (Раздел 2.4)
4. **ER Diagram** — Схема базы данных (Раздел 4.3)
5. **State Diagram: Сообщение** — sent → delivered → read (Раздел 7.4)
6. **Flowchart: Деплой** — Пошаговый процесс deploy.sh (Раздел 13.2)
7. **Flowchart: Troubleshooting** — Decision tree для диагностики (Раздел 18.1)
8. **Sequence Diagram: WebSocket подключение** — Connect → Auth → Subscribe (Раздел 9.2)

---

## План написания

1. Разделы 1-2: Введение + Архитектура
2. Раздел 3: Настройка окружения
3. Разделы 4-5: База данных + Бэкенд
4. Раздел 6: API-контракты
5. Разделы 7-8: Бизнес-логика + Безопасность
6. Разделы 9-10: WebSocket + Фронтенд
7. Разделы 11-12: Docker + Nginx
8. Разделы 13-14: Деплой + Бэкапы
9. Разделы 15-16: CI/CD + Тестирование
10. Разделы 17-18: Мониторинг + Troubleshooting
11. Раздел 19: Приложение
