# 📡 API

## Обзор

Base URL: `/api`
Формат: JSON
Аутентификация: JWT в HttpOnly cookie или `Authorization: Bearer <token>`

## Auth

### POST /api/auth/login

Вход пользователя.

**Request:** `{"username": "str", "password": "str"}`
**Response 200:** `{"access_token": "jwt", "token_type": "bearer"}`
**Errors:** 401 (Invalid credentials), 403 (Banned)

### POST /api/auth/register

Регистрация по invite-коду.

**Request:** `{"username": "str", "password": "str", "invite_code": "str"}`
**Response 201:** `{"access_token": "jwt", "token_type": "bearer"}`
**Errors:** 400 (Invalid invite, username taken)

### GET /api/auth/me

Данные текущего пользователя.

**Response 200:** `{"id": 1, "username": "str", "avatar_path": null, "is_active": true}`
**Errors:** 401 (Not authenticated)

### PUT /api/auth/me

Обновление профиля.

**Request:** `{"username": "str"}`
**Response 200:** User object
**Errors:** 400 (Username taken), 401

### POST /api/auth/invite

Генерация invite-кода.

**Response 200:** `{"code": "A1B2C3D4"}`

### POST /api/auth/logout

Выход (удаление cookie).

**Response 200:** `{"message": "Logged out"}`

## Chats

### POST /api/chats

Создание чата.

**Request:** `{"type": "group", "name": "str", "description": "str", "member_ids": [2, 3]}`
**Response 201:** Chat object с member_count

### GET /api/chats

Список чатов пользователя (sorted by updated_at DESC).

**Response 200:** Array of Chat

### GET /api/chats/{chat_id}

Информация о чате.

**Response 200:** Chat
**Errors:** 404

### DELETE /api/chats/{chat_id}

Удаление чата (только админ).

**Response 204**

### GET /api/chats/{chat_id}/members

Список участников.

**Response 200:** Array of ChatMemberResponse

### POST /api/chats/{chat_id}/members

Добавление участника (только админ).

**Request:** `{"user_id": 5, "role": "member"}`
**Response 201:** ChatMemberResponse

### DELETE /api/chats/{chat_id}/members/{user_id}

Удаление участника (админ или сам себя).

**Response 204**

### PUT /api/chats/{chat_id}/members/{user_id}/role

Смена роли (только админ).

**Request:** `{"role": "admin"}`
**Response 200:** ChatMemberResponse

## Messages

### POST /api/chats/{chat_id}/messages

Отправка сообщения.

**Request:** `{"content": "str"}`
**Response 201:** MessageResponse

### GET /api/chats/{chat_id}/messages

Сообщения с пагинацией.

**Query:** `page=1`, `per_page=50` (1-100)
**Response 200:** `{"messages": [...], "total": 150, "page": 1, "per_page": 50, "has_next": true}`

### GET /api/chats/{chat_id}/messages/search

Поиск по тексту.

**Query:** `q=str` (1-200 chars)
**Response 200:** `{"messages": [...], "total": 5, "query": "str"}`

### DELETE /api/chats/{chat_id}/messages/{message_id}

Удаление сообщения (автор или админ, soft delete).

**Response 204**

## Files

### POST /api/files/{chat_id}/upload

Загрузка файла.

**Content-Type:** multipart/form-data
**Response 201:** `{"message_id": 1, "file_path": "str", "file_mime": "str", "file_size": 1024}`
**Errors:** 400 (Invalid MIME), 413 (Too large >25MB)

### GET /api/files/{chat_id}/{file_path}

Скачивание файла.

**Response 200:** File stream
**Errors:** 403 (Access denied), 404

## WebSocket

### GET /ws?token=<jwt>

Real-time подключение.

**Протокол:**
```json
// Подписка: {"action": "subscribe", "chat_id": 1}
// Отписка: {"action": "unsubscribe", "chat_id": 1}
// Сообщение: {"action": "message", "chat_id": 1, "content": "Hello"}
// Прочитано: {"action": "mark_read", "chat_id": 1, "message_id": 5}
// Ping: {"action": "ping"} → {"type": "pong"}
```

**События:**
```json
// Новое сообщение: {"type": "new_message", "chat_id": 1, "message": {...}}
// Прочитано: {"type": "message_read", "chat_id": 1, "message_id": 5, "read_by": 2}
```
