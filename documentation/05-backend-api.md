# Раздел 5: Бэкенд (FastAPI)

## 5.1. Точка входа

Файл [`main.py`](messenger/main.py) — центральная точка входа FastAPI приложения.

### Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Инициализация и завершение работы приложения."""
    # Startup
    logger.info("Starting messenger...")
    await init_db()
    
    yield
    
    # Shutdown
    logger.info("Shutting down messenger...")
```

**Этапы startup:**
1. Логирование конфигурации (log level, debug mode)
2. Настройка Loguru (stderr + файл с ротацией)
3. Создание директорий (`data/`, `uploads/`, `logs/`)
4. Инициализация БД (`init_db()`)

## 5.2. Конфигурация

Файл [`config.py`](messenger/config.py) использует `pydantic-settings` для загрузки переменных окружения:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # ... поля ...
    
    @model_validator(mode="after")
    def check_jwt_secret(self) -> "Settings":
        if self.jwt_secret_key == "change-me-in-production" and not self.debug:
            raise ValueError("JWT_SECRET_KEY must be changed...")
        return self
```

**Ключевые особенности:**
- Case-insensitive имена переменных
- Автоматическая загрузка из `.env`
- Валидация JWT_SECRET_KEY при startup

### CORS origins property

```python
@property
def cors_origins_list(self) -> list[str]:
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```

Строка из `.env` парсится в список: `"http://a,http://b"` → `["http://a", "http://b"]`

## 5.3. Middleware

### 5.3.1. CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)
```

**Параметры:**
- `allow_credentials=True` — отправка cookies с кросс-доменными запросами
- `max_age=3600` — кэширование preflight запросов на 1 час

### 5.3.2. Security Headers

```python
@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    if "server" in response.headers:
        del response.headers["server"]
    
    return response
```

**Описание headers:**

| Header | Значение | Назначение |
|--------|----------|------------|
| X-Content-Type-Options | nosniff | Запрет MIME-sniffing |
| X-Frame-Options | DENY | Запрет встраивания в iframe |
| X-XSS-Protection | 1; mode=block | Встроенная XSS защита браузера |
| Referrer-Policy | strict-origin-when-cross-origin | Контроль передачи Referer |
| Permissions-Policy | camera=(), microphone=() | Отключение API устройства |
| Strict-Transport-Security | max-age=31536000 | Принудительный HTTPS |

### 5.3.3. Rate Limiting

```python
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_requests}/{settings.rate_limit_seconds}s"],
)
```

**Параметры по умолчанию:**
- 5 запросов в секунду на IP
- Обработчик 429 ошибки возвращает JSON: `{"detail": "Rate limit exceeded. Try again later."}`

## 5.4. Логирование

Используется **Loguru** с конфигурацией:

```python
logger.remove(0)  # Удаление default handler
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)

# Файловый логгер
logger.add(
    log_dir / "messenger_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    enqueue=True,  # Thread-safe очередь
)
```

**Формат логов:**
```
2024-01-15 10:30:00 | INFO     | messenger.api.auth:login - User admin logged in
```

## 5.5. Health Check

```python
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
```

Используется Docker healthcheck:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

## 5.6. Dependency Injection

FastAPI DI паттерн используется повсеместно:

```python
# В роутерах
async def get_me(current_user: User = Depends(get_current_user)):
    ...

# get_current_user зависит от get_session
async def get_current_user(
    token: str | None = Cookie(default=None, alias="access_token"),
    session: AsyncSession = Depends(get_session),
) -> User:
    ...
```

**Переопределение в тестах:**
```python
app.dependency_overrides[get_session] = override_get_session
```

---

# Раздел 6: API-контракты

## 6.1. Обзор API

| Параметр | Значение |
|----------|----------|
| Base URL | `/api` |
| Формат | JSON |
| Аутентификация | JWT в HttpOnly cookie или `Authorization: Bearer` header |
| Кодировка | UTF-8 |

### Префиксы роутеров

| Префикс | Тег | Описание |
|---------|-----|----------|
| `/api/auth` | auth | Аутентификация |
| `/api/chats` | chats | Чаты и сообщения |
| `/api/files` | files | Файлы |
| `/api/users` | users | Пользователи |
| `/ws` | websocket | WebSocket |

## 6.2. Аутентификация (`/api/auth`)

### POST /api/auth/login

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
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Response 401:** Invalid credentials
**Response 403:** User is banned

**Side effects:** Установка HttpOnly cookie `access_token`

### POST /api/auth/register

**Request:**
```json
{
  "username": "string (2-50 chars)",
  "password": "string (6-128 chars)",
  "invite_code": "string (1-50 chars)"
}
```

**Response 201:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Response 400:** Invalid invite code / Username already taken

### GET /api/auth/me

**Response 200:**
```json
{
  "id": 1,
  "username": "admin",
  "avatar_path": null,
  "is_active": true
}
```

**Response 401:** Not authenticated / Invalid token
**Response 403:** User is banned

### PUT /api/auth/me

**Request:**
```json
{
  "username": "string (2-50 chars, optional)"
}
```

**Response 200:** Updated user object
**Response 400:** Username already taken

### POST /api/auth/invite

**Response 200:**
```json
{
  "code": "A7X9K2M1"
}
```

### POST /api/auth/logout

**Response 200:**
```json
{
  "message": "Logged out"
}
```

**Side effects:** Удаление cookie `access_token`

## 6.3. Пользователи (`/api/users`)

### GET /api/users/search

**Query parameters:**
| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `q` | string | required | Поисковый запрос (1-50 chars) |
| `limit` | int | 20 | Максимум результатов (1-100) |

**Response 200:**
```json
[
  {
    "id": 2,
    "username": "alice",
    "is_active": true
  },
  {
    "id": 3,
    "username": "alex",
    "is_active": true
  }
]
```

**Примечание:** Текущий пользователь исключается из результатов. Поиск case-insensitive.

**Response 401:** Not authenticated
**Response 422:** Validation error (empty query)

## 6.4. Чаты (`/api/chats`)

### POST /api/chats

**Request:**
```json
{
  "type": "group | personal",
  "name": "string (optional, max 200)",
  "description": "string (optional, max 1000)",
  "member_ids": [2, 3, 4]
}
```

**Response 201:**
```json
{
  "id": 1,
  "type": "group",
  "name": "Team Chat",
  "description": null,
  "avatar_path": null,
  "created_at": "2024-01-15T10:00:00",
  "updated_at": "2024-01-15T10:00:00",
  "member_count": 4
}
```

### GET /api/chats

**Response 200:** Array of ChatResponse, sorted by updated_at desc

### GET /api/chats/{id}

**Response 200:** ChatResponse
**Response 404:** Chat not found (user is not a member)

### DELETE /api/chats/{id}

**Response 204:** No content
**Response 403:** Only chat admin can delete
**Response 404:** Chat not found

### GET /api/chats/{id}/members

**Response 200:**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "username": "admin",
    "role": "admin",
    "joined_at": "2024-01-15T10:00:00"
  }
]
```

### POST /api/chats/{id}/members

**Request:**
```json
{
  "user_id": 5,
  "role": "member | admin"
}
```

**Response 201:** ChatMemberResponse
**Response 403:** Only chat admin can add members
**Response 404:** User not found
**Response 400:** User is already a member

### DELETE /api/chats/{id}/members/{user_id}

**Response 204:** No content
**Response 403:** Not allowed (not admin and not self)
**Response 404:** Member not found

### PUT /api/chats/{id}/members/{user_id}/role

**Request:**
```json
{
  "role": "admin | member"
}
```

**Response 200:** ChatMemberResponse
**Response 403:** Only chat admin can change roles

## 6.5. Сообщения

### POST /api/chats/{id}/messages

**Request:**
```json
{
  "content": "string (max 10000 chars)"
}
```

**Response 201:**
```json
{
  "id": 1,
  "chat_id": 1,
  "sender_id": 1,
  "sender_username": "admin",
  "content": "Hello!",
  "file_path": null,
  "file_mime": null,
  "file_size": null,
  "status": "sent",
  "created_at": "2024-01-15T10:00:00"
}
```

### GET /api/chats/{id}/messages

**Query parameters:**
| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `page` | int | 1 | Номер страницы (≥1) |
| `per_page` | int | 50 | Сообщений на страницу (1-100) |

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

### GET /api/chats/{id}/messages/search

**Query parameters:**
| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `q` | string | required | Поисковый запрос (1-200 chars) |

**Response 200:**
```json
{
  "messages": [...],
  "total": 5,
  "query": "hello"
}
```

### DELETE /api/chats/{id}/messages/{message_id}

**Response 204:** No content (soft-delete)
**Response 403:** Not allowed (not author and not admin)
**Response 404:** Message not found

## 6.6. Файлы (`/api/files`)

### POST /api/files/{chat_id}/upload

**Content-Type:** `multipart/form-data`

**Response 201:**
```json
{
  "message_id": 5,
  "file_path": "1/abc123.jpg",
  "file_mime": "image/jpeg",
  "file_size": 102400
}
```

**Response 413:** File too large (max 25MB)
**Response 400:** File type not allowed / Empty file
**Response 404:** Chat not found

### GET /api/files/{chat_id}/{file_path}

**Response 200:** File binary
**Response 403:** Access denied (path traversal)
**Response 404:** File not found / Chat not found

## 6.7. WebSocket (`/ws`)

### Подключение

```
GET /ws?token=<jwt_token>
```

### Протокол

**Клиент → Сервер:**
```json
{"action": "subscribe", "chat_id": 1}
{"action": "unsubscribe", "chat_id": 1}
{"action": "message", "chat_id": 1, "content": "Hello"}
{"action": "mark_read", "chat_id": 1, "message_id": 5}
{"action": "ping"}
```

**Сервер → Клиент:**
```json
{"type": "subscribed", "chat_id": 1}
{"type": "new_message", "chat_id": 1, "message": {...}}
{"type": "message_read", "chat_id": 1, "message_id": 5, "read_by": 2}
{"type": "pong"}
{"type": "error", "message": "Unknown action: foo"}
```

### Коды закрытия

| Код | Описание |
|-----|----------|
| 4001 | Missing token |
| 4002 | Invalid token |
| 4003 | Invalid payload |

## 6.8. Коды ошибок

| HTTP Status | Описание |
|-------------|----------|
| 200 | OK |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request (validation, business logic) |
| 401 | Unauthorized (not authenticated) |
| 403 | Forbidden (banned, not admin) |
| 404 | Not Found |
| 413 | Payload Too Large |
| 422 | Unprocessable Entity (validation) |
| 429 | Too Many Requests (rate limit) |

## 6.9. Pydantic схемы

### Auth schemas ([`auth.py`](messenger/schemas/auth.py))

```python
class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str = Field(min_length=1, max_length=50)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    avatar_path: str | None = None
    is_active: bool

class UserSearchResponse(BaseModel):
    id: int
    username: str
    is_active: bool
```

### Chat schemas ([`chat.py`](messenger/schemas/chat.py))

```python
class ChatCreate(BaseModel):
    type: ChatType = ChatType.group
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    member_ids: list[int] = Field(default_factory=list)

class ChatResponse(BaseModel):
    id: int
    type: ChatType
    name: str | None
    description: str | None
    avatar_path: str | None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

class MessageCreate(BaseModel):
    content: str | None = Field(default=None, max_length=10000)

class MessageResponse(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    sender_username: str
    content: str | None
    file_path: str | None
    file_mime: str | None
    file_size: int | None
    status: MessageStatus
    created_at: datetime

class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
```
