# Раздел 14: Бэкапы и восстановление

## 14.1. Стратегия бэкапов

### Что бэкапится

| Данные | Путь | Метод |
|--------|------|-------|
| База данных | `./data/app.db` | sqlite3 `.backup` |
| Файлы | `./data/uploads/` | Копирование файлов |
| Логи | `./data/logs/` | Опционально |

### Частота

| Тип | Частота | Хранение |
|-----|---------|----------|
| Ручной бэкап | По требованию | 30 дней |
| Автоматический (cron) | Ежедневно | 30 дней |

### Ротация

```bash
find "$BACKUP_DIR" -name "app_*.db*" -mtime +30 -delete
```

Файлы старше 30 дней автоматически удаляются.

## 14.2. Скрипт backup.sh

[`scripts/backup.sh`](scripts/backup.sh):

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
DB_FILE="$PROJECT_DIR/data/app.db"
TIMESTAMP="$(date +%F_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/app_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

# Проверка существования БД
if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: Database file not found: $DB_FILE"
    exit 1
fi

# Бэкап через sqlite3 .backup (безопасный метод)
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"
    echo "Backup created successfully via sqlite3"
else
    # Fallback: копирование с остановкой приложения
    cp "$DB_FILE" "$BACKUP_FILE"
    [ -f "${DB_FILE}-wal" ] && cp "${DB_FILE}-wal" "${BACKUP_FILE}-wal"
    [ -f "${DB_FILE}-shm" ] && cp "${DB_FILE}-shm" "${BACKUP_FILE}-shm"
fi

# Сжатие бэкапа
if command -v gzip &> /dev/null; then
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
fi

# Очистка старых бэкапов (>30 дней)
find "$BACKUP_DIR" -name "app_*.db*" -mtime +30 -delete 2>/dev/null || true

echo "Backup complete: $BACKUP_FILE"
```

### Методы бэкапа

| Метод | Когда | Описание |
|-------|-------|----------|
| `sqlite3 .backup` | sqlite3 установлен | Online backup без остановки приложения |
| File copy | sqlite3 недоступен | Требует остановки приложения |

**Почему `.backup` лучше `cp`:**
- Консистентная копия (checkpoint WAL)
- Работает без остановки приложения
- Игнорирует временные файлы

## 14.3. Скрипт restore.sh

[`scripts/restore.sh`](scripts/restore.sh):

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="$1"
DB_FILE="$PROJECT_DIR/data/app.db"

# Проверка аргументов
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Предупреждение
echo "WARNING: This will overwrite the current database!"
read -p "Are you sure? (y/N): " -n 1 -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Остановка приложения
docker compose down

# Распаковка если нужно
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
fi

# Восстановление
sqlite3 "$DB_FILE" ".restore '$TEMP_FILE'"

# Настройка WAL режима
sqlite3 "$DB_FILE" "PRAGMA journal_mode=WAL;"
sqlite3 "$DB_FILE" "PRAGMA synchronous=NORMAL;"
sqlite3 "$DB_FILE" "PRAGMA foreign_keys=ON;"

# Запуск приложения
docker compose up -d
```

**Безопасность:**
- Подтверждение перед восстановлением
- Остановка приложения перед записью
- Восстановление WAL режима после

## 14.4. Makefile команды

```bash
# Создать бэкап
make backup

# Восстановить из бэкапа
make restore BACKUP_FILE=./backups/app_2024-01-01_120000.db.gz
```

## 14.5. Автоматические бэкапы

### Cron job

[`scripts/cron-backup.sh`](scripts/cron-backup.sh):

```bash
#!/usr/bin/env bash
# Добавить в crontab:
# 0 2 * * * /opt/messenger/scripts/cron-backup.sh

cd /opt/messenger
./scripts/backup.sh >> /var/log/messenger-backup.log 2>&1
```

### Crontab

```bash
# Ежедневно в 2:00
0 2 * * * /opt/messenger/scripts/backup.sh >> /var/log/messenger-backup.log 2>&1
```

## 14.6. Проверка целостности

```bash
# SQLite integrity check
sqlite3 ./data/app.db "PRAGMA integrity_check;"

# Ожидается: "ok"
```

**Автоматическая проверка после restore:**
```bash
sqlite3 "$DB_FILE" "PRAGMA integrity_check;" | grep -q "ok"
if [ $? -ne 0 ]; then
    echo "ERROR: Database integrity check failed"
    exit 1
fi
```

---

# Раздел 15: CI/CD и качество кода

## 15.1. Pre-commit hooks

[`.pre-commit-config.yaml`](.pre-commit-config.yaml):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic
          - pydantic-settings
          - sqlmodel
          - fastapi
          - types-python-jose
          - types-aiofiles
        exclude: ^tests/
```

**Установка:**
```bash
make hooks
# или
pre-commit install
```

**Запуск вручную:**
```bash
pre-commit run --all-files
```

## 15.2. Линтинг

**Ruff** — быстрый линтер на Rust, замена flake8 + isort + pyupgrade.

Конфигурация ([`pyproject.toml`](pyproject.toml)):
```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
```

**Правила:**
| Код | Описание |
|-----|----------|
| E | PEP8 style errors |
| F | Pyflakes (unused imports, undefined names) |
| I | isort (сортировка импортов) |
| N | pep8-naming (имена переменных/функций) |
| W | PEP8 warnings |
| UP | pyupgrade (современный синтаксис) |
| B | flake8-bugbear (частые баги) |
| SIM | flake8-simplify (упрощение кода) |

**Команды:**
```bash
make lint    # Проверка
make format  # Автофикс
```

## 15.3. Типизация

**MyPy** — статическая проверка типов.

Конфигурация:
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Команда:**
```bash
make typecheck
# или
mypy messenger/
```

**Исключения:**
- Тесты (`exclude: ^tests/`) — не проверяются в pre-commit
- Динамические паттерны FastAPI DI — `type: ignore` где необходимо

## 15.4. Форматирование

**Ruff format** — замена black.

```bash
make format
# или
ruff format messenger/ tests/
```

**Настройки:**
- Line length: 120
- Indent: 4 spaces
- Quotes: double

## 15.5. Git hooks

### post-merge

[`hooks/post-merge`](hooks/post-merge):

```bash
#!/usr/bin/env bash
# Запуск тестов при merge в main

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" = "main" ]; then
    echo "Running tests after merge to main..."
    make test
    
    if [ $? -ne 0 ]; then
        echo "Tests failed! Reverting merge..."
        git reset --hard HEAD@{1}
        exit 1
    fi
    
    echo "Tests passed!"
fi
```

**Установка:**
```bash
cp hooks/post-merge .git/hooks/post-merge
chmod +x .git/hooks/post-merge
```

## 15.6. CI/CD Pipeline

### Рекомендуемая конфигурация (GitHub Actions)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry
      - run: poetry install --with dev
      - run: make lint
      - run: make typecheck

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry
      - run: poetry install --with dev
      - run: make test-cov

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build
      - run: docker compose up -d
      - run: sleep 10
      - run: curl -f http://localhost:8001/health
```

---

# Раздел 16: Тестирование

## 16.1. Обзор

**Фреймворки:**
- pytest — основной фреймворк
- pytest-asyncio — асинхронные тесты
- httpx — HTTP клиент для тестирования API

**Конфигурация:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = ["ignore::DeprecationWarning"]

[tool.coverage.run]
source = ["messenger"]
omit = ["tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if __name__ == .__main__.:"]
fail_under = 80
```

## 16.2. Фикстуры

[`conftest.py`](tests/conftest.py):

### Тестовая БД

```python
_test_engine = None

def get_test_engine():
    global _test_engine
    if _test_engine is None:
        _test_engine = create_async_engine(
            "sqlite+aiosqlite://",  # In-memory
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _test_engine
```

**Особенности:**
- In-memory SQLite (без файловой системы)
- `StaticPool` — один connection для всех тестов
- Singleton engine — таблицы создаются один раз

### Фикстуры

| Фикстура | Scope | Описание |
|----------|-------|----------|
| `setup_test_db` | session | Создание таблиц один раз |
| `test_session` | function | Очищенная сессия БД |
| `client` | function | AsyncClient без авторизации |
| `auth_client` | function | AsyncClient с Bearer token |
| `test_user` | function | Тестовый пользователь |
| `test_user_data` | function | Данные пользователя (dict) |

### Очистка таблиц

```python
async def _clear_all_tables(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM messages"))
    await session.execute(text("DELETE FROM chat_members"))
    await session.execute(text("DELETE FROM chats"))
    await session.execute(text("DELETE FROM invite_codes"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()
```

## 16.3. Тестовая БД

**Инициализация:**
```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    engine = get_test_engine()
    
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    
    asyncio.get_event_loop().run_until_complete(_setup())
    yield
```

**Переопределение DI:**
```python
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    engine = get_test_engine()
    
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()
```

## 16.4. Тесты аутентификации

[`test_auth.py`](tests/test_auth.py):

### TestAuthLogin

| Тест | Описание |
|------|----------|
| `test_login_success` | Успешный логин |
| `test_login_wrong_password` | Неверный пароль → 401 |
| `test_login_nonexistent_user` | Несуществующий пользователь → 401 |
| `test_login_banned_user` | Забаненный пользователь → 403 |

### TestAuthRegister

| Тест | Описание |
|------|----------|
| `test_register_success` | Успешная регистрация → 201 |
| `test_register_invalid_invite` | Несуществующий код → 400 |
| `test_register_duplicate_username` | Занятый username → 400 |
| `test_register_used_invite` | Использованный код → 400 |

### TestAuthMe

| Тест | Описание |
|------|----------|
| `test_get_me_authenticated` | Данные пользователя → 200 |
| `test_get_me_no_token` | Без токена → 401 |
| `test_get_me_invalid_token` | Невалидный токен → 401 |

### TestAuthProfile

| Тест | Описание |
|------|----------|
| `test_update_username` | Смена username → 200 |
| `test_update_duplicate_username` | Занятый username → 400 |

### TestAuthInvite

| Тест | Описание |
|------|----------|
| `test_generate_invite` | Генерация кода → 200 |

### TestAuthLogout

| Тест | Описание |
|------|----------|
| `test_logout` | Выход → 200 |

## 16.5. Тесты чатов

[`test_chat_api.py`](tests/test_chat_api.py):

| Тест | Описание |
|------|----------|
| `test_create_chat` | Создание чата → 201 |
| `test_list_chats` | Список чатов пользователя |
| `test_get_chat` | Информация о чате |
| `test_get_chat_not_member` | Чужой чат → 404 |
| `test_delete_chat` | Удаление чата админом → 204 |
| `test_delete_chat_not_admin` | Удаление не админом → 403 |
| `test_add_member` | Добавление участника → 201 |
| `test_add_member_not_admin` | Добавление не админом → 403 |
| `test_remove_member` | Удаление участника → 204 |
| `test_send_message` | Отправка сообщения → 201 |
| `test_get_messages` | Получение сообщений с пагинацией |
| `test_search_messages` | Поиск по тексту |
| `test_delete_message` | Удаление сообщения → 204 |

## 16.6. Тесты безопасности

[`test_security.py`](tests/test_security.py):

| Тест | Описание |
|------|----------|
| `test_hash_password` | Argon2id хеширование |
| `test_verify_password_correct` | Верный пароль → True |
| `test_verify_password_wrong` | Неверный пароль → False |
| `test_create_access_token` | Создание JWT |
| `test_decode_access_token` | Декодирование JWT |
| `test_expired_token` | Истекший токен → None |
| `test_generate_invite_code` | Генерация кода (длина, формат) |

## 16.7. Тесты моделей

[`test_models.py`](tests/test_models.py):

| Тест | Описание |
|------|----------|
| `test_user_creation` | Создание пользователя |
| `test_chat_creation` | Создание чата |
| `test_message_creation` | Создание сообщения |
| `test_invite_code_creation` | Создание invite-кода |
| `test_chat_member_creation` | Создание участника |

## 16.8. Health check тесты

[`test_health.py`](tests/test_health.py):

```python
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
```

## 16.9. Coverage

**Требование:** 80%+

```bash
make test-cov
# poetry run pytest tests/ -v --cov=messenger --cov-report=term-missing --cov-report=html
```

**Отчёт:**
- Terminal: таблица с пропущенными строками
- HTML: `htmlcov/index.html` — интерактивный отчёт

## 16.10. Запуск тестов

```bash
# Все тесты
make test

# С coverage
make test-cov

# Конкретный файл
poetry run pytest tests/test_auth.py -v

# Конкретный тест
poetry run pytest tests/test_auth.py::TestAuthLogin::test_login_success -v

# С отладкой
poetry run pytest tests/ -v --pdb
```
