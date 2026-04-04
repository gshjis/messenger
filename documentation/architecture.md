# 🏗️ Архитектура

## Общая схема

```mermaid
graph TB
    Client["📱 Клиент (Vue 3 PWA)"]
    subgraph Frontend
        AuthView["AuthView<br/>Login/Register"]
        ChatView["ChatView<br/>Sidebar+Messages"]
        Stores["Pinia Stores<br/>auth, chat"]
        WS["WebSocket<br/>Connection"]
    end
    Client --> Frontend

    subgraph Backend["⚙️ Backend (FastAPI)"]
        AuthAPI["Auth API<br/>/api/auth"]
        ChatAPI["Chat API<br/>/api/chats"]
        FilesAPI["Files API<br/>/api/files"]
        WSHandler["WebSocket<br/>Handler"]
        Security["🔒 Security Layer<br/>JWT + argon2id + rate limit"]
        DBLayer["🗄️ Database Layer<br/>SQLModel"]
    end

    Frontend -->|HTTP + WebSocket| Backend
    AuthView --> AuthAPI
    ChatView --> ChatAPI
    WS --> WSHandler

    subgraph Database["💾 SQLite (WAL)"]
        Users["users"]
        Chats["chats"]
        Messages["messages"]
        Members["chat_members"]
        Invites["invite_codes"]
    end

    DBLayer --> Database
```

## Компоненты

### Backend (Python + FastAPI)

| Модуль | Файл | Описание |
|--------|------|----------|
| `main.py` | Точка входа | Lifespan, middleware (CORS, security headers, rate limiting), роутеры |
| `config.py` | Настройки | Pydantic Settings, загрузка из .env, валидация JWT_SECRET_KEY |
| `database.py` | БД | SQLite engine (singleton), WAL режим, async сессии с rollback |
| `models/` | Модели | SQLModel: User, Chat, ChatMember, Message, InviteCode |
| `schemas/` | Схемы | Pydantic: запросы/ответы API |
| `api/` | REST | Auth, Chat, Files endpoints |
| `websockets/` | WS | ConnectionManager, handler (subscribe, message, mark_read, ping) |
| `security/` | Auth | argon2id хеширование, JWT encode/decode, invite генерация |

### Frontend (Vue 3 + Vite PWA)

| Модуль | Файл | Описание |
|--------|------|----------|
| `main.js` | Инициализация | Vue app, Pinia, Router |
| `App.vue` | Корень | Автозагрузка пользователя при старте |
| `router.js` | Маршруты | `/auth` (guest), `/` (auth required) |
| `stores/auth.js` | Auth store | login, register, fetchMe, updateProfile, generateInvite, logout |
| `stores/chat.js` | Chat store | fetchChats, createChat, selectChat, fetchMessages, sendMessage |
| `views/AuthView.vue` | Логин/Регистрация | Формы с переключением |
| `views/ChatView.vue` | Чат | Sidebar, сообщения, WebSocket, профиль, темы |

## Потоки данных

### Аутентификация

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Auth API
    participant DB as Database
    participant JWT as JWT

    C->>A: POST /api/auth/register
    A->>DB: Проверка invite
    DB-->>A: Код валиден
    A->>DB: Создание User (argon2id)
    A->>JWT: Создание токена
    JWT-->>A: Token
    A-->>C: 201 + Set-Cookie (HttpOnly)

    C->>A: POST /api/auth/login
    A->>DB: Проверка пароля
    DB-->>A: User найден
    A->>JWT: Создание токена
    A-->>C: 200 + Set-Cookie

    C->>A: GET /api/auth/me
    A->>JWT: Decode cookie
    JWT-->>A: user_id
    A->>DB: Запрос User
    DB-->>A: User
    A-->>C: 200 + User data
```

### Отправка сообщения (REST)

```mermaid
sequenceDiagram
    participant C as Client
    participant CA as Chat API
    participant DB as Database

    C->>CA: POST /api/chats/{id}/messages
    CA->>DB: Проверка членства
    DB-->>CA: Участник найден
    CA->>DB: Создание Message
    CA->>DB: Обновление chat.updated_at
    DB-->>CA: OK
    CA-->>C: 201 + Message
```

### Отправка сообщения (WebSocket)

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as WebSocket Handler
    participant CM as ConnectionManager
    participant DB as Database

    C->>WS: WS /ws?token=xxx
    WS->>WS: JWT decode
    WS->>CM: connect(user_id)
    CM-->>WS: OK
    WS-->>C: Connected

    C->>WS: {"action":"subscribe","chat_id":1}
    WS->>CM: subscribe(user_id, chat_id)
    CM-->>WS: OK
    WS-->>C: {"type":"subscribed"}

    C->>WS: {"action":"message","chat_id":1,"content":"Hi"}
    WS->>CM: is_subscribed?
    CM-->>WS: Yes
    WS->>DB: Создание Message
    DB-->>WS: OK
    WS->>CM: broadcast_to_chat(chat_id=1)
    CM->>C: {"type":"new_message","message":{...}}
```

### Статусы сообщений

```mermaid
stateDiagram-v2
    [*] --> sent: Сообщение создано
    sent --> delivered: Получатель онлайн (WS)
    delivered --> read: Получатель открыл чат
    sent --> read: mark_read action
```

## Зависимости

### Backend
```
fastapi → starlette (ASGI) → uvicorn (сервер)
sqlmodel → sqlalchemy 2.0 (ORM) + pydantic (валидация)
argon2-cffi → хеширование паролей
python-jose → JWT encode/decode
python-magic → MIME проверка файлов
slowapi → rate limiting
loguru → логирование
aiosqlite → async SQLite драйвер
```

### Frontend
```
vue 3 → реактивный фреймворк (Composition API)
pinia → state management
vue-router → маршрутизация с guards
vite → сборщик
vite-plugin-pwa → PWA manifest + service worker
```
