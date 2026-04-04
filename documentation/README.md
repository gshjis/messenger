# 📘 Документация Messenger

Полная техническая документация личного мессенджера — self-hosted решения на базе Python + FastAPI + Vue 3 PWA.

## Оглавление

| Раздел | Файл | Описание |
|--------|------|----------|
| 🏗️ Архитектура | [architecture.md](architecture.md) | Общая схема, компоненты, потоки данных, зависимости |
| 🗄️ База данных | [database.md](database.md) | Модели, схемы таблиц, связи, индексы, перечисления |
| 📡 API | [api.md](api.md) | REST эндпоинты, WebSocket протокол, примеры |
| 🔒 Безопасность | [security.md](security.md) | JWT, argon2id, rate limiting, security headers |
| 🚀 Развёртывание | [deployment.md](deployment.md) | Docker Compose, systemd, nginx, бэкапы |
| 💻 Разработка | [development.md](development.md) | Структура, тесты, CI/CD, гайдлайны |

## Краткое описание

**Messenger** — личный мессенджер для закрытой группы (5–15 человек). Self-hosted, полностью контролируемый владельцем.

### Ключевые возможности
- Авторизация по invite-коду
- Личные и групповые чаты (до 20 чел)
- Текст, эмодзи, фото, документы (до 25 МБ)
- Real-time через WebSocket
- PWA (установка на телефон)
- Тёмная/светлая тема

### Стек
| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.12 + FastAPI |
| ORM/БД | SQLModel + SQLite (WAL) |
| Auth | JWT (HttpOnly cookie) + argon2id |
| Frontend | Vue 3 + Vite + PWA |
| Прокси | Caddy (авто-HTTPS) |
| Контейнеризация | Docker Compose |
