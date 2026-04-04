# 🏗️ Архитектура системы

## Общая схема

```mermaid
graph TB
    Client[📱 Клиент — Vue 3 PWA]
    Caddy[🌐 Caddy Proxy :443/:80]
    Frontend[🖥️ Nginx :80 — статика]
    Backend[⚙️ FastAPI :8000]
    DB[(💾 SQLite WAL)]
    Uploads[📁 /data/uploads]
    Logs[📋 /data/logs]

    Client -->|HTTPS| Caddy
    Caddy -->|/| Frontend
    Caddy -->|/api/*| Backend
    Caddy -->|/ws| Backend
    Backend --> DB
    Backend --> Uploads
    Backend --> Logs
```

## Компоненты

### Backend (Python + FastAPI)

| Модуль | Файл | Описание |
|--------|------|----------|
| `main.py` | Точка входа, lifespan, middleware, роутеры |
| `config.py` | Настройки из .env через pydantic-settings |
| `database.py` | SQLite engine, WAL режим, сессии |
| `models/` | SQLModel модели данных |
| `schemas/` | Pydantic схемы для API |
| `api/` | REST endpoints |
| `websockets/` | WebSocket менеджер и обработчик |
| `security/` | JWT, argon2id, rate limiting |

### Frontend (Vue 3 + Vite PWA)

| Модуль | Файл | Описание |
|--------|------|----------|
| `main.js` | Инициализация Vue, Pinia, Router |
| `App.vue` | Корневой компонент |
| `router.js` | Маршруты /auth, / |
| `stores/auth.js` | Auth store (login, register, profile) |
| `stores/chat.js` | Chat store (chats, messages, WS) |
| `views/AuthView.vue` | Страница логина/регистрации |
| `views/ChatView.vue` | Sidebar + Chat + WebSocket |

## Потоки данных

### Аутентификация

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API /auth
    participant DB as SQLite
    participant JWT as JWT

    C->>A: POST /api/auth/register
    A->>DB: Проверка invite-кода
    DB-->>A: Код валиден
    A->>DB: Создание пользователя (argon2id hash)
    A->>JWT: Создание токена (sub=user_id)
    JWT-->>A: Token
    A-->>C: 201 + Set-Cookie (HttpOnly)
```

### Отправка сообщения

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as WebSocket
    participant CM as ConnectionManager
    participant API as API /chats
    participant DB as SQLite

    C->>WS: {"action":"message","chat_id":1,"content":"Hi"}
    WS->>CM: broadcast_to_chat(chat_id=1)
    CM->>C: {"type":"new_message",...}
    WS->>API: Сохранение в БД
    API->>DB: INSERT INTO messages
    DB-->>API: OK
```

## Зависимости

### Backend

```
fastapi ──┬── starlette (ASGI)
          ├── pydantic (валидация)
          └── uvicorn (сервер)

sqlmodel ─┬── sqlalchemy 2.0 (ORM)
          └── pydantic (схемы)

argon2-cffi ── хеширование паролей
python-jose ── JWT encode/decode
python-magic ── MIME проверка файлов
slowapi ── rate limiting
loguru ── логирование
```

### Frontend

```
vue 3 ── реактивный фреймворк
pinia ── state management
vue-router ── маршрутизация
vite ── сборщик
vite-plugin-pwa ── PWA manifest + service worker
```

## Диаграмма классов

```mermaid
classDiagram
    class User {
        +int id
        +str username
        +str hashed_password
        +str avatar_path
        +bool is_active
        +bool is_banned
        +datetime created_at
    }

    class Chat {
        +int id
        +ChatType type
        +str name
        +str description
        +str avatar_path
        +datetime created_at
    }

    class ChatMember {
        +int id
        +int chat_id
        +int user_id
        +MemberRole role
        +datetime joined_at
    }

    class Message {
        +int id
        +int chat_id
        +int sender_id
        +str content
        +str file_path
        +str file_mime
        +int file_size
        +MessageStatus status
        +bool is_deleted
        +datetime created_at
    }

    class InviteCode {
        +int id
        +str code
        +int max_uses
        +int used_count
        +int created_by
        +bool is_active
        +datetime created_at
    }

    User "1" --> "*" ChatMember : состоит в
    Chat "1" --> "*" ChatMember : имеет
    Chat "1" --> "*" Message : содержит
    User "1" --> "*" Message : отправляет
    User "1" --> "*" InviteCode : создаёт
```
