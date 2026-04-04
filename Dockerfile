# Stage 1: Установка зависимостей
FROM python:3.12-slim AS deps

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install --no-cache-dir poetry==1.8.3

WORKDIR /app

# Копирование только файлов зависимостей (кеш при изменении кода)
COPY pyproject.toml poetry.lock ./

# Установка только production зависимостей
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --without dev

# Stage 2: Production
FROM python:3.12-slim AS runtime

# Только runtime зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 app

WORKDIR /app

# Копирование зависимостей из deps
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Копирование только кода приложения (без тестов, docs и т.д.)
COPY messenger/ ./messenger/

# Создание директорий
RUN mkdir -p /app/data/uploads /app/data/logs \
    && chown -R app:app /app/data

USER app

EXPOSE 8000

CMD ["uvicorn", "messenger.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
