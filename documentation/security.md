# 🔒 Безопасность

## Обзор

| Уровень | Механизм | Описание |
|---------|----------|----------|
| Транспорт | HTTPS (Caddy) | Авто-сертификаты Let's Encrypt |
| Аутентификация | JWT + argon2id | Токены в HttpOnly cookie |
| Авторизация | ChatMember role | admin/member роли |
| Файлы | python-magic | MIME проверка + лимит 25 МБ |
| Rate Limiting | slowapi | 5 запросов/сек на IP |
| Headers | Security middleware | X-Frame-Options, CSP, HSTS |

## Шифрование

### Пароли

- **Алгоритм:** argon2id (рекомендация OWASP 2024)
- **Параметры:** time_cost=3, memory_cost=65536, parallelism=4
- **Соль:** автоматическая, 16 байт

```python
from argon2 import PasswordHasher
ph = PasswordHasher()
hashed = ph.hash(password)
ph.verify(hashed, password)
```

### JWT токены

- **Алгоритм:** HS256
- **Срок жизни:** 7 дней (настраивается)
- **Хранение:** HttpOnly cookie (защита от XSS)
- **Payload:** `{"sub": "user_id", "exp": timestamp}`

```python
from jose import jwt
token = jwt.encode({"sub": str(user_id), "exp": expire}, secret, algorithm="HS256")
payload = jwt.decode(token, secret, algorithms=["HS256"])
```

## Управление ключами

| Ключ | Хранение | Ротация |
|------|----------|---------|
| JWT_SECRET_KEY | .env (не в git) | При компрометации |
| SSL сертификаты | Caddy volume | Авто (90 дней) |
| БД | SQLite файл | Бэкапы |

## Аутентификация

### Flow

1. Пользователь получает invite-код от админа
2. Регистрируется с кодом
3. Получает JWT в HttpOnly cookie
4. Все запросы с cookie
5. WebSocket через token query параметр

### Invite-коды

| Параметр | Значение |
|----------|----------|
| Длина | 8 символов (A-Z, 0-9) |
| Макс. использований | 1 (настраивается) |
| Алфавит | 36 символов |
| Энтропия | ~41 бит |

## Авторизация

### Роли

| Роль | Права |
|------|-------|
| admin | Создание/удаление чата, управление участниками, удаление сообщений |
| member | Отправка/чтение сообщений |

### Проверки

- Каждый endpoint проверяет членство в чате
- Админские действия проверяют роль
- Файлы проверяют принадлежность чату

## Rate Limiting

| Endpoint | Лимит |
|----------|-------|
| Все API | 5 req/sec на IP |
| Health | Без лимита |
| WebSocket | Без лимита |

## Обработка уязвимостей

### SQL-инъекции

- Используется ORM (SQLModel) — параметризованные запросы
- Поиск: `Message.content.like()` с экранированием `%`, `_`, `\`

### XSS

- Vue 3 автоматически экранирует `{{ }}`
- Content валидируется на сервере

### Path Traversal

- Имена файлов: UUID + санитизация
- Скачивание: `.resolve()` + `startswith()` проверка

### CSRF

- SameSite=Lax cookie
- Для API можно добавить CSRF token

## Security Headers

| Header | Значение |
|--------|----------|
| X-Content-Type-Options | nosniff |
| X-Frame-Options | DENY |
| X-XSS-Protection | 1; mode=block |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | camera=(), microphone=(), geolocation=() |
| Strict-Transport-Security | max-age=31536000; includeSubDomains |
