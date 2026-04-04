# 🏗️ Архитектура

## Общая схема

```
┌─────────────────────────────────────────────────────────────┐
│                        Клиент (Vue 3 PWA)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │AuthView  │  │ChatView  │  │Pinia     │  │WebSocket    │ │
│  │(Login/   │  │(Sidebar+ │  │Stores    │  │Connection   │ │
│  │Register) │  │Messages) │  │(auth,    │  │Manager      │ │
│  │          │  │          │  │ chat)    │  │             │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │Auth API  │  │Chat API  │  │Files API │  │WebSocket    │ │
│  │/api/auth │  │/api/chats│  │/api/files│  │Handler      │ │
│  │          │  │          │  │          │  │             │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Security Layer                            │ │
│  │  JWT (HttpOnly cookie) + argon2id + rate limiting     │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Database Layer (SQLModel)                  │ │
│  │  User, Chat, ChatMember, Message, InviteCode           │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     SQLite (WAL mode)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │users     │  │chats     │  │messages  │  │chat_members │ │
│  │          │  │          │  │          │  │             │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              invite_codes                              │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
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

```
Client → POST /api/auth/register → Проверка invite → Создание User → JWT → Set-Cookie
Client → POST /api/auth/login → Проверка пароля → JWT → Set-Cookie
Client → GET /api/auth/me → Cookie → JWT decode → User из БД
```

### Отправка сообщения (REST)

```
Client → POST /api/chats/{id}/messages → Проверка членства → Создание Message → Обновление chat.updated_at → Response
```

### Отправка сообщения (WebSocket)

```
Client → WS /ws?token=xxx → JWT decode → connect()
Client → {"action":"subscribe","chat_id":1} → subscribe()
Client → {"action":"message","chat_id":1,"content":"Hi"} → Проверка подписки → Создание Message → broadcast_to_chat()
Server → {"type":"new_message","chat_id":1,"message":{...}} → Все подписчики
```

### Статусы сообщений

```
sent → delivered (при получении WS) → read (при mark_read или открытии чата)
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
