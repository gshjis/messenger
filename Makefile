.PHONY: up down backup restore logs test lint install clean

# ============================================
# Messenger — Makefile
# ============================================

# Запуск всех сервисов
up:
	docker compose up -d --build

# Сборка с нуля без кеша
build:
	docker compose build --no-cache
	docker compose up -d

# Остановка всех сервисов
down:
	docker compose down

# Перезапуск
restart: down up

# Логи приложения
logs:
	docker compose logs -f app --tail=100

# Логи всех сервисов
logs-all:
	docker compose logs -f --tail=100

# Бэкап БД
backup:
	@mkdir -p ./backups
	@echo "Creating backup..."
	docker compose exec app sqlite3 /app/data/app.db ".backup /app/data/backup_$$(date +%F_%H%M%S).db" || \
		sqlite3 ./data/app.db ".backup ./backups/app_$$(date +%F_%H%M%S).db"
	@echo "Backup created in ./backups/"

# Восстановление из бэкапа (укажите BACKUP_FILE=path)
restore:
ifndef BACKUP_FILE
	@echo "Usage: make restore BACKUP_FILE=./backups/app_2024-01-01.db"
	@exit 1
endif
	@echo "Restoring from $(BACKUP_FILE)..."
	docker compose down
	sqlite3 ./data/app.db ".restore $(BACKUP_FILE)"
	docker compose up -d
	@echo "Restore complete"

# Запуск тестов
test:
	poetry run pytest tests/ -v --tb=short

# Запуск тестов с coverage
test-cov:
	poetry run pytest tests/ -v --cov=messenger --cov-report=term-missing --cov-report=html

# Линтинг
lint:
	poetry run ruff check messenger/ tests/

# Форматирование
format:
	poetry run ruff check messenger/ tests/ --fix
	poetry run ruff format messenger/ tests/

# Проверка типов
typecheck:
	poetry run mypy messenger/

# Установка зависимостей
install:
	poetry install

# Установка pre-commit hooks
hooks:
	poetry run pre-commit install

# Очистка
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf *.egg-info/
	@echo "Cleaned up cache files"

# Полная очистка (включая data)
clean-all: clean
	rm -rf data/
	rm -rf backups/
	@echo "Cleaned up all generated files"

# Помощь
help:
	@echo "Available commands:"
	@echo "  make build       - Build from scratch without cache"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View app logs"
	@echo "  make logs-all    - View all service logs"
	@echo "  make backup      - Create database backup"
	@echo "  make restore     - Restore from backup (BACKUP_FILE=path)"
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage"
	@echo "  make lint        - Run linter"
	@echo "  make format      - Format code"
	@echo "  make typecheck   - Run type checker"
	@echo "  make install     - Install dependencies"
	@echo "  make hooks       - Install pre-commit hooks"
	@echo "  make clean       - Clean cache files"
	@echo "  make clean-all   - Clean all generated files"
	@echo "  make help        - Show this help"
