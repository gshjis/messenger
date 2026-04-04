# 📡 API Specification

## Обзор

Base URL: `/api`
Формат: JSON
Аутентификация: JWT в HttpOnly cookie или `Authorization: Bearer <token>`

## Версионирование

Текущая версия: v1 (без префикса в URL)
При изменении API будет добавляться `/api/v2/...`

## Аутентификация

| Метод | Описание |
|-------|----------|
| Cookie | `access_token` (HttpOnly, Secure, SameSite=Lax) |
| Header | `Authorization: Bearer <token>` |

## Endpoints

### Auth

#### POST /api/auth/login

Вход пользователя.

**Request:**
```json
{
  "username": "string (2-50 chars)",
  "password": "string (6-128 chars)"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

**Errors:**
| Код | Описание |
|-----|----------|
| 401 | Invalid credentials |
| 403 | User is banned |
| 422 | Validation error |

---

#### POST /api/auth/register

Регистрация по invite-коду.

**Request:**
```json
{
  "username": "string (2-50 chars)",
  "password": "string (6-128 chars)",
  "invite_code": "string"
}
```

**Response 201:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

**Errors:**
| Код | Описание |
|-----|----------|
| 400 | Invalid/used invite code, username taken |
| 422 | Validation error |

---

#### GET /api/auth/me

Получение данных текущего пользователя.

**Response 200:**
```json
{
  "id": 1,
  "username": "testuser",
  "avatar_path": null,
  "is_active": true
}
```

**Errors:**
| Код | Описание |
|-----|----------|
| 401 | Not authenticated |

---

#### PUT /api/auth/me

Обновление профиля.

**Request:**
```json
{
  "username": "newname"
}
```

**Response 200:** User object

**Errors:**
| Код | Описание |
|-----|----------|
| 400 | Username already taken |
| 401 | Not authenticated |

---

#### POST /api/auth/invite

Генерация invite-кода.

**Response 200:**
```json
{
  "code": "A1B2C3D4"
}
```

---

#### POST /api/auth/logout

Выход (удаление cookie).

**Response 200:**
```json
{
  "message": "Logged out"
}
```

### Chats

#### POST /api/chats

Создание чата.

**Request:**
```json
{
  "type": "group",
  "name": "My Group",
  "description": "Optional description",
  "member_ids": [2, 3]
}
```

**Response 201:**
```json
{
  "id": 1,
  "type": "group",
  "name": "My Group",
  "description": "Optional description",
  "avatar_path": null,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "member_count": 3
}
```

---

#### GET /api/chats

Список чатов пользователя.

**Response 200:** Array of Chat objects

---

#### GET /api/chats/{chat_id}

Информация о чате.

**Response 200:** Chat object

**Errors:**
| Код | Описание |
|-----|----------|
| 404 | Chat not found |

---

#### DELETE /api/chats/{chat_id}

Удаление чата (только админ).

**Response 204:** No content

---

#### GET /api/chats/{chat_id}/members

Список участников.

**Response 200:**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "username": "admin",
    "role": "admin",
    "joined_at": "2024-01-01T00:00:00"
  }
]
```

---

#### POST /api/chats/{chat_id}/members

Добавление участника (только админ).

**Request:**
```json
{
  "user_id": 5,
  "role": "member"
}
```

**Response 201:** ChatMemberResponse

---

#### DELETE /api/chats/{chat_id}/members/{user_id}

Удаление участника.

**Response 204:** No content

---

#### PUT /api/chats/{chat_id}/members/{user_id}/role

Смена роли (только админ).

**Request:**
```json
{
  "role": "admin"
}
```

**Response 200:** ChatMemberResponse

### Messages

#### POST /api/chats/{chat_id}/messages

Отправка сообщения.

**Request:**
```json
{
  "content": "Hello, world!"
}
```

**Response 201:**
```json
{
  "id": 1,
  "chat_id": 1,
  "sender_id": 1,
  "sender_username": "testuser",
  "content": "Hello, world!",
  "file_path": null,
  "file_mime": null,
  "file_size": null,
  "status": "sent",
  "created_at": "2024-01-01T00:00:00"
}
```

---

#### GET /api/chats/{chat_id}/messages

Получение сообщений с пагинацией.

**Query params:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| page | int | 1 | Номер страницы |
| per_page | int | 50 | Сообщений на страницу (1-100) |

**Response 200:**
```json
{
  "messages": [...],
  "total": 150,
  "page": 1,
  "per_page": 50,
  "has_next": true
}
```

---

#### GET /api/chats/{chat_id}/messages/search

Поиск по тексту.

**Query params:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| q | string (1-200) | Поисковый запрос |

**Response 200:**
```json
{
  "messages": [...],
  "total": 5,
  "query": "Find"
}
```

---

#### DELETE /api/chats/{chat_id}/messages/{message_id}

Удаление сообщения (автор или админ).

**Response 204:** No content

### Files

#### POST /api/files/{chat_id}/upload

Загрузка файла.

**Content-Type:** `multipart/form-data`

**Response 201:**
```json
{
  "message_id": 1,
  "file_path": "1/uuid.jpg",
  "file_mime": "image/jpeg",
  "file_size": 102400
}
```

**Errors:**
| Код | Описание |
|-----|----------|
| 400 | Invalid MIME type |
| 413 | File too large (>25MB) |

---

#### GET /api/files/{chat_id}/{file_path}

Скачивание файла.

**Response 200:** File stream

**Errors:**
| Код | Описание |
|-----|----------|
| 403 | Access denied |
| 404 | File not found |

### WebSocket

#### GET /ws?token=<jwt>

Real-time подключение.

**Протокол:**
```json
// Подписка на чат
{"action": "subscribe", "chat_id": 1}

// Отправка сообщения
{"action": "message", "chat_id": 1, "content": "Hello"}

// Отметка прочитанным
{"action": "mark_read", "chat_id": 1, "message_id": 5}

// Ping
{"action": "ping"}
// Response: {"type": "pong"}
```

**Получаемые события:**
```json
// Новое сообщение
{
  "type": "new_message",
  "chat_id": 1,
  "message": {...}
}

// Сообщение прочитано
{
  "type": "message_read",
  "chat_id": 1,
  "message_id": 5,
  "read_by": 2
}
```
