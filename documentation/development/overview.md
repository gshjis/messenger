# 💻 Разработка

## Гайдлайны по коду

### Python

- **Стиль:** PEP 8, line-length 120
- **Типизация:** Обязательная для всех функций
- **Форматирование:** Ruff
- **Линтинг:** Ruff + MyPy

```python
# Хорошо
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Информация о чате."""
    ...

# Плохо
async def get_chat(chat_id, current_user, session):
    ...
```

### Frontend

- **Стиль:** Vue 3 Composition API
- **State:** Pinia stores
- **CSS:** CSS variables для тем

## Структура репозитория

```
messenger/
├── messenger/              # Backend
│   ├── __init__.py
│   ├── main.py             # Точка входа
│   ├── config.py           # Настройки
│   ├── database.py         # БД
│   ├── models/             # SQLModel модели
│   ├── schemas/            # Pydantic схемы
│   ├── api/                # REST endpoints
│   ├── websockets/         # WebSocket handlers
│   ├── security/           # Auth
│   └── utils/              # Утилиты
├── frontend/               # Vue 3 PWA
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router.js
│       ├── style.css
│       ├── stores/
│       └── views/
├── tests/                  # Тесты
├── scripts/                # Скрипты (backup, restore)
├── documentation/          # Документация
├── Dockerfile
├── docker-compose.yml
├── Caddyfile
├── nginx.conf
├── Makefile
├── pyproject.toml
└── .env.example
```

## Тестирование

### Структура тестов

```
tests/
├── conftest.py             # Фикстуры
├── test_health.py          # Health endpoint
├── test_models.py          # Модели данных
├── test_auth.py            # Аутентификация
├── test_chat_api.py        # API чатов
└── test_security.py        # Безопасность
```

### Запуск

```bash
make test       # Все тесты
make test-cov   # С coverage (80%+)
```

### Фикстуры

| Фикстура | Описание |
|----------|----------|
| `test_engine` | In-memory SQLite engine |
| `test_session` | Тестовая сессия БД |
| `client` | HTTP клиент без авторизации |
| `auth_client` | HTTP клиент с Authorization header |
| `test_user` | Тестовый пользователь |

### Стратегия

- **Unit:** Модели, валидация, security функции
- **Integration:** API endpoints через TestClient
- **Security:** Rate limiting, CORS, auth

## CI/CD

### Pre-commit hooks

```bash
make hooks    # Установка pre-commit
```

Хуки:
- `ruff` — линтинг + автофикс
- `ruff-format` — форматирование
- `mypy` — проверка типов

### Git workflow

```
main ────────────────────────────────────────
  │         │         │
  ├─ feature/auth ────┘
  ├─ feature/models ──┘
  └─ feature/chats ───┘
```

- Feature ветки: `feature/<name>`
- Merge в main через PR
- Тесты запускаются при merge (post-merge hook)

## Внесение изменений

### 1. Создание ветки

```bash
git checkout -b feature/new-feature
```

### 2. Разработка

```bash
make test     # Тесты
make lint     # Линтинг
make format   # Форматирование
```

### 3. Коммит

```bash
git add -A
git commit -m "feat: описание изменения"
```

### 4. Merge

```bash
git checkout main
git merge feature/new-feature
# Тесты запустятся автоматически
```

## Makefile команды

| Команда | Описание |
|---------|----------|
| `make up` | Запуск всех сервисов |
| `make down` | Остановка |
| `make build` | Сборка без кеша |
| `make restart` | Перезапуск |
| `make logs` | Логи приложения |
| `make backup` | Бэкап БД |
| `make restore` | Восстановление |
| `make test` | Тесты |
| `make test-cov` | Тесты с coverage |
| `make lint` | Линтинг |
| `make format` | Форматирование |
| `make clean` | Очистка кеша |
