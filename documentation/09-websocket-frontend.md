# Раздел 9: Real-time коммуникация (WebSocket)

## 9.1. Архитектура WebSocket

### ConnectionManager

Класс [`ConnectionManager`](messenger/websockets/manager.py:9) управляет всеми активными WebSocket-подключениями:

```python
class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> WebSocket
        self._active_connections: dict[int, WebSocket] = {}
        # chat_id -> set[user_id]
        self._chat_subscriptions: dict[int, set[int]] = defaultdict(set)
        # user_id -> set[chat_id]
        self._user_subscriptions: dict[int, set[int]] = defaultdict(set)
```

**Структуры данных:**

| Структура | Тип | Назначение |
|-----------|-----|------------|
| `_active_connections` | dict[user_id, WebSocket] | Быстрый поиск WebSocket по user_id |
| `_chat_subscriptions` | dict[chat_id, set[user_id]] | Fan-out рассылка всем подписчикам чата |
| `_user_subscriptions` | dict[user_id, set[chat_id]] | Быстрая проверка подписок пользователя |

### Глобальный экземпляр

```python
manager = ConnectionManager()
```

Единый экземпляр на всё приложение (singleton через module-level variable).

## 9.2. Протокол подключения

### Шаг 1: Подключение

```
GET /ws?token=<jwt_token>
```

Токен передаётся в query parameter (не в cookie, т.к. WebSocket API не поддерживает custom headers при подключении из браузера).

### Шаг 2: Аутентификация

```python
token = websocket.query_params.get("token")
if not token:
    await websocket.close(code=4001, reason="Missing token")
    return

payload = decode_access_token(token)
if payload is None:
    await websocket.close(code=4002, reason="Invalid token")
    return
```

### Шаг 3: Регистрация подключения

```python
await manager.connect(websocket, user_id)
```

### Коды закрытия

| Код | Причина | Когда |
|-----|---------|-------|
| 4001 | Missing token | Token не передан в query |
| 4002 | Invalid token | JWT невалиден или истёк |
| 4003 | Invalid payload | В токене нет `sub` |

## 9.3. Управление подписками

### Подписка

```json
{"action": "subscribe", "chat_id": 1}
```

```python
def subscribe(self, user_id: int, chat_id: int) -> None:
    self._chat_subscriptions[chat_id].add(user_id)
    self._user_subscriptions[user_id].add(chat_id)
```

### Отписка

```json
{"action": "unsubscribe", "chat_id": 1}
```

```python
def unsubscribe(self, user_id: int, chat_id: int) -> None:
    self._chat_subscriptions[chat_id].discard(user_id)
    self._user_subscriptions[user_id].discard(chat_id)
    
    # Очистка пустых множеств
    if not self._chat_subscriptions[chat_id]:
        del self._chat_subscriptions[chat_id]
    if not self._user_subscriptions[user_id]:
        del self._user_subscriptions[user_id]
```

### Отписка при отключении

```python
async def disconnect(self, user_id: int) -> None:
    ws = self._active_connections.pop(user_id, None)
    
    # Удалить из всех подписок
    for chat_id in list(self._user_subscriptions.get(user_id, set())):
        self._chat_subscriptions[chat_id].discard(user_id)
        if not self._chat_subscriptions[chat_id]:
            del self._chat_subscriptions[chat_id]
    
    self._user_subscriptions.pop(user_id, None)
```

## 9.4. Рассылка сообщений

### Broadcast всем подписчикам чата

```python
async def broadcast_to_chat(
    self, 
    chat_id: int, 
    message: dict, 
    exclude_user_id: int | None = None
) -> int:
    subscribers = self._chat_subscriptions.get(chat_id, set()).copy()
    delivered = 0
    
    for user_id in subscribers:
        if user_id == exclude_user_id:
            continue
        
        ws = self._active_connections.get(user_id)
        if ws is None:
            continue
        
        try:
            await ws.send_json(message)
            delivered += 1
        except Exception:
            await self.disconnect(user_id)
    
    return delivered
```

**Особенности:**
- `.copy()` — предотвращает modification during iteration
- `exclude_user_id` — отправитель не получает своё сообщение обратно
- При ошибке отправки — автоматический disconnect

### Персональное сообщение

```python
async def send_personal_message(self, user_id: int, message: dict) -> bool:
    ws = self._active_connections.get(user_id)
    if ws is None:
        return False
    try:
        await ws.send_json(message)
        return True
    except Exception:
        await self.disconnect(user_id)
        return False
```

Используется для уведомлений `message_read`.

## 9.5. Обработчики действий

### message — отправка сообщения

```python
async def handle_message(data: dict, user_id: int) -> None:
    chat_id = data.get("chat_id")
    content = data.get("content")
    
    if chat_id is None or content is None:
        return
    
    # Проверка подписки
    if not manager.is_subscribed(user_id, chat_id):
        return
    
    # Сохранение в БД
    async for session in get_session():
        # Проверка участника
        result = await session.exec(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == user_id,
            )
        )
        if result.first() is None:
            return
        
        # Создание сообщения
        message = Message(chat_id=chat_id, sender_id=user_id, content=content)
        session.add(message)
        
        # Обновление updated_at чата
        chat.updated_at = datetime.now(timezone.utc)
        
        await session.commit()
        await session.refresh(message)
        
        # Broadcast
        broadcast_data = {
            "type": "new_message",
            "chat_id": chat_id,
            "message": {
                "id": message.id,
                "chat_id": message.chat_id,
                "sender_id": message.sender_id,
                "sender_username": username,
                "content": message.content,
                "file_path": message.file_path,
                "file_mime": message.file_mime,
                "file_size": message.file_size,
                "status": message.status,
                "created_at": message.created_at.isoformat(),
            },
        }
        
        await manager.broadcast_to_chat(chat_id, broadcast_data, exclude_user_id=user_id)
        break
```

### mark_read — отметка прочитанного

```python
async def handle_mark_read(data: dict, user_id: int) -> None:
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    
    async for session in get_session():
        if message_id:
            # Конкретное сообщение
            message = await session.get(Message, message_id)
            if message:
                message.status = MessageStatus.read
                await session.commit()
                
                await manager.send_personal_message(
                    message.sender_id,
                    {
                        "type": "message_read",
                        "chat_id": chat_id,
                        "message_id": message.id,
                        "read_by": user_id,
                    },
                )
        else:
            # Все сообщения в чате от других пользователей
            result = await session.exec(
                select(Message).where(
                    Message.chat_id == chat_id,
                    Message.sender_id != user_id,
                    Message.status != MessageStatus.read,
                )
            )
            messages = result.all()
            for msg in messages:
                msg.status = MessageStatus.read
                await manager.send_personal_message(
                    msg.sender_id,
                    {
                        "type": "message_read",
                        "chat_id": chat_id,
                        "message_id": msg.id,
                        "read_by": user_id,
                    },
                )
            await session.commit()
        break
```

### ping/pong — keepalive

```python
elif action == "ping":
    await websocket.send_json({"type": "pong"})
```

## 9.6. Reconnection

Клиент реализует автоматическое переподключение:

```javascript
ws.onclose = () => {
    console.log('WebSocket closed, reconnecting...')
    reconnectTimer = setTimeout(connectWebSocket, 3000)
}
```

**Задержка:** 3 секунды

**При переподключении:**
1. Новый токен (если истёк — редирект на логин)
2. Подписка на все чаты пользователя
3. Потерянные сообщения не восстанавливаются через WS (только через REST)

## 9.7. Масштабируемость

### Текущие ограничения

| Параметр | Значение | Причина |
|----------|----------|---------|
| Контейнеры бэкенда | 1 | In-memory manager не шардится |
| Макс. подключений | Зависит от RAM | ~10K на 512MB |
| Fan-out | O(n) на чат | Linear scan подписчиков |

### Пути масштабирования

**Redis Pub/Sub:**
```python
# Вместо in-memory manager
import redis.asyncio as redis

r = redis.Redis()

async def broadcast_to_chat(chat_id, message):
    await r.publish(f"chat:{chat_id}", json.dumps(message))

# Подписка
async def subscribe_to_chat(chat_id):
    pubsub = r.pubsub()
    await pubsub.subscribe(f"chat:{chat_id}")
    async for msg in pubsub.listen():
        yield msg["data"]
```

**WebSocket Gateway:**
- Отдельный сервис для WS подключений
- Общение с бэкендом через Redis/HTTP
- Горизонтальное масштабирование gateway

---

# Раздел 10: Фронтенд (Vue 3 PWA)

## 10.1. Обзор

**Технологии:**
- Vue 3 Composition API (`<script setup>`)
- Vite 6 — сборка и dev-сервер
- Pinia — state management
- Vue Router 4 — клиентский роутинг
- vite-plugin-pwa — Progressive Web App

**Структура:**
```
frontend/
├── src/
│   ├── App.vue              # Корневой компонент
│   ├── main.js              # Точка входа
│   ├── router.js            # Маршруты
│   ├── style.css            # Глобальные стили
│   ├── stores/
│   │   ├── auth.js          # Auth store
│   │   └── chat.js          # Chat store
│   └── views/
│       ├── AuthView.vue     # Логин/регистрация
│       └── ChatView.vue     # Основной интерфейс
├── index.html               # HTML шаблон
├── vite.config.js           # Vite конфигурация
├── package.json             # Зависимости
├── Dockerfile               # Multi-stage build
└── nginx.conf               # Nginx для статики
```

## 10.2. Структура проекта

### Точка входа ([`main.js`](frontend/src/main.js))

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

## 10.3. Роутинг

[`router.js`](frontend/src/router.js):

```javascript
const routes = [
  { path: '/auth', component: AuthView, meta: { guest: true } },
  { path: '/', component: ChatView, meta: { requiresAuth: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory('/messenger/'),
  routes
})
```

### Navigation Guards

```javascript
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/auth')
  } else if (to.meta.guest && token) {
    next('/')
  } else {
    next()
  }
})
```

**Логика:**
| Маршрут | Token | Результат |
|---------|-------|-----------|
| `/auth` | Нет | Разрешить |
| `/auth` | Есть | Редирект на `/` |
| `/` | Есть | Разрешить |
| `/` | Нет | Редирект на `/auth` |

**Base path:** `/messenger/` — для production за nginx location.

## 10.4. State Management (Pinia)

### 10.4.1. Auth Store ([`auth.js`](frontend/src/stores/auth.js))

```javascript
export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || null)
  const isAuthenticated = computed(() => !!token.value)
  
  // Methods
  async function login(username, password) { ... }
  async function register(username, password, inviteCode) { ... }
  async function fetchMe() { ... }
  async function updateProfile(username) { ... }
  async function generateInvite() { ... }
  async function searchUsers(query, limit = 20) { ... }
  function logout() { ... }
  
  return { user, token, isAuthenticated, login, register, fetchMe, updateProfile, generateInvite, searchUsers, logout }
})
```

**State:**
| Поле | Тип | Источник |
|------|-----|----------|
| `user` | object\|null | `GET /api/auth/me` |
| `token` | string\|null | `localStorage` |
| `isAuthenticated` | boolean | Computed от `token` |

### 10.4.2. Chat Store ([`chat.js`](frontend/src/stores/chat.js))

```javascript
export const useChatStore = defineStore('chat', () => {
  const chats = ref([])
  const currentChat = ref(null)
  const messages = ref([])
  const members = ref([])
  const loading = ref(false)
  const page = ref(1)
  const hasMore = ref(true)
  
  // Methods
  async function fetchChats(token) { ... }
  async function createChat(data, token) { ... }
  async function selectChat(chatId, token) { ... }
  async function fetchMessages(token) { ... }
  async function fetchMembers(token) { ... }
  async function sendMessage(content, token) { ... }
  function addMessage(msg) { ... }
  function reset() { ... }
  
  return { chats, currentChat, messages, members, loading, page, hasMore, ... }
})
```

**State:**
| Поле | Тип | Описание |
|------|-----|----------|
| `chats` | array | Список чатов пользователя |
| `currentChat` | object\|null | Активный чат |
| `messages` | array | Сообщения текущего чата |
| `members` | array | Участники текущего чата |
| `loading` | boolean | Флаг загрузки сообщений |
| `page` | number | Текущая страница пагинации |
| `hasMore` | boolean | Есть ли ещё сообщения |

## 10.5. Компоненты

### 10.5.1. App.vue

```vue
<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth.js'

const auth = useAuthStore()

onMounted(async () => {
  if (auth.token) {
    await auth.fetchMe()
  }
})
</script>
```

**Роль:** Инициализация данных пользователя при загрузке.

### 10.5.2. AuthView.vue

**Функционал:**
- Переключение login/register форм
- Валидация ввода
- Отображение ошибок
- Редирект после успешной аутентификации

```vue
<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>💬 Messenger</h1>
      
      <!-- Login form -->
      <div v-if="isLogin">
        <input v-model="username" ... />
        <input v-model="password" type="password" ... />
        <button @click="handleLogin">Login</button>
      </div>
      
      <!-- Register form -->
      <div v-else>
        <input v-model="username" ... />
        <input v-model="password" type="password" ... />
        <input v-model="inviteCode" ... />
        <button @click="handleRegister">Register</button>
      </div>
    </div>
  </div>
</template>
```

### 10.5.3. ChatView.vue

**Функционал:**
- Sidebar со списком чатов
- Поиск пользователей
- Окно чата с сообщениями
- Отправка сообщений
- Модальные окна (создание чата, профиль)
- Переключение темы
- WebSocket подключение

**Структура:**
```vue
<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">...</div>
      
      <!-- User Search -->
      <div class="user-search">
        <input v-model="searchQuery" @input="handleSearch" />
        <div v-if="searchResults.length > 0" class="search-results">
          <div v-for="user in searchResults" @click="selectUser(user)">
            {{ user.username }}
          </div>
        </div>
      </div>
      
      <div class="chat-list">...</div>
      <div class="user-menu">...</div>
    </div>
    
    <!-- Chat Window -->
    <div class="chat-window">
      <div class="chat-header">...</div>
      <div class="messages-container">...</div>
      <div class="message-input">...</div>
    </div>
    
    <!-- Modals -->
    <div v-if="showCreateChat" class="modal-overlay">...</div>
    <div v-if="showProfile" class="modal-overlay">...</div>
  </div>
</template>
```

## 10.6. WebSocket клиент

```javascript
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${window.location.host}/messenger/ws?token=${auth.token}`)
  
  ws.onopen = () => {
    // Subscribe to all chats
    chatStore.chats.forEach(chat => {
      ws.send(JSON.stringify({ action: 'subscribe', chat_id: chat.id }))
    })
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'new_message') {
      chatStore.addMessage(data.message)
      scrollToBottom()
    }
  }
  
  ws.onclose = () => {
    reconnectTimer = setTimeout(connectWebSocket, 3000)
  }
}
```

**Обработанные события:**
| Server → Client | Действие |
|-----------------|----------|
| `new_message` | Добавление сообщения в список |
| Другие типы | Игнорируются (MVP) |

**Не обработанные (MVP):**
- `message_read` — уведомления о прочтении
- `subscribed` — подтверждение подписки
- `error` — ошибки сервера
- `pong` — ответ на ping

## 10.7. PWA

### Конфигурация ([`vite.config.js`](frontend/vite.config.js))

```javascript
VitePWA({
  registerType: 'autoUpdate',
  includeAssets: ['favicon.ico', 'apple-touch-icon.png'],
  manifest: {
    name: 'Messenger',
    short_name: 'Messenger',
    description: 'Личный мессенджер',
    theme_color: '#1a1a2e',
    background_color: '#1a1a2e',
    display: 'standalone',
    icons: [
      { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }
    ]
  }
})
```

### Установка на устройство

**Android (Chrome):**
1. Откройте мессенджер в Chrome
2. Нажмите "⋮" → "Установить приложение"

**iOS (Safari):**
1. Откройте мессенджер в Safari
2. Нажмите "Поделиться" → "На экран «Домой»"

### Ограничения iOS PWA

| Функция | iOS | Android |
|---------|-----|---------|
| Push-уведомления | ❌ Ограничены | ✅ Работают |
| WebSocket | ✅ Работает | ✅ Работает |
| Background sync | ❌ Не поддерживается | ✅ Работает |
| Offline cache | ✅ Service Worker | ✅ Service Worker |

## 10.8. Темы

```javascript
const theme = ref(localStorage.getItem('theme') || 'dark')
document.documentElement.setAttribute('data-theme', theme.value)

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem('theme', theme.value)
  document.documentElement.setAttribute('data-theme', theme.value)
}
```

**CSS variables:**
```css
:root {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-tertiary: #0f3460;
  --text-primary: #e4e4e4;
  --text-secondary: #a0a0a0;
  --border: #2a2a4a;
  --error: #e74c3c;
  --success: #2ecc71;
}

[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-tertiary: #e0e0e0;
  --text-primary: #1a1a1a;
  --text-secondary: #666666;
  --border: #dddddd;
}
```

## 10.9. Сборка и деплой

### Dev-сервер

```bash
cd frontend
npm run dev
# http://localhost:5173
```

**Прокси (vite.config.js):**
```javascript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true
    }
  }
}
```

### Production build

```bash
npm run build
# dist/ — готовые статические файлы
```

### Docker build

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

## 10.10. Статус реализации фронтенда

### 10.10.1. Таблица соответствия API endpoints

| Endpoint | Реализован | Файл | Примечание |
|----------|:----------:|------|------------|
| `POST /api/auth/login` | ✅ | `stores/auth.js:13` | Основной логин |
| `POST /api/auth/register` | ✅ | `stores/auth.js:27` | Регистрация по invite |
| `GET /api/auth/me` | ✅ | `stores/auth.js:45` | Fetch при загрузке |
| `PUT /api/auth/me` | ✅ | `stores/auth.js:57` | Обновление профиля |
| `POST /api/auth/invite` | ✅ | `stores/auth.js:70` | Генерация invite |
| `POST /api/auth/logout` | ❌ | — | Только очистка localStorage |
| `GET /api/users/search` | ✅ | `stores/auth.js:78` | Поиск пользователей |
| `POST /api/chats` | ✅ | `stores/chat.js:23` | Создание чата |
| `GET /api/chats` | ✅ | `stores/chat.js:16` | Список чатов |
| `GET /api/chats/{id}` | ❌ | — | Не используется отдельно |
| `DELETE /api/chats/{id}` | ❌ | — | Нет UI |
| `GET /api/chats/{id}/members` | ✅ | `stores/chat.js:71` | При выборе чата |
| `POST /api/chats/{id}/members` | ❌ | — | Нет UI добавления |
| `DELETE /api/chats/{id}/members/{user_id}` | ❌ | — | Нет UI удаления |
| `PUT /api/chats/{id}/members/{user_id}/role` | ❌ | — | Нет UI смены роли |
| `POST /api/chats/{id}/messages` | ✅ | `stores/chat.js:79` | Отправка |
| `GET /api/chats/{id}/messages` | ✅ | `stores/chat.js:52` | С пагинацией |
| `GET /api/chats/{id}/messages/search` | ❌ | — | Нет UI поиска |
| `DELETE /api/chats/{id}/messages/{id}` | ❌ | — | Нет UI удаления |
| `POST /api/files/{chat_id}/upload` | ❌ | — | Нет UI загрузки |
| `GET /api/files/{chat_id}/{file_path}` | ❌ | — | Нет UI скачивания |
| `GET /health` | ❌ | — | Не используется |
| `WebSocket /ws` | ✅ | `ChatView.vue:163` | new_message только |

### 10.10.2. Реализованный функционал

- ✅ Аутентификация (login, register, me, update profile, invite)
- ✅ Список чатов
- ✅ Создание чатов
- ✅ Отправка и получение сообщений (REST + WebSocket)
- ✅ Пагинация сообщений
- ✅ Поиск пользователей
- ✅ Переключение темы
- ✅ Автоматический reconnect WebSocket

### 10.10.3. Нереализованный функционал

- ❌ Удаление чатов
- ❌ Удаление сообщений
- ❌ Добавление участников в чат
- ❌ Удаление участников из чата
- ❌ Смена ролей участников
- ❌ Поиск по сообщениям
- ❌ Загрузка файлов
- ❌ Скачивание файлов
- ❌ Админ-панель (бан, удаление пользователей)
- ❌ Статусы сообщений (delivered/read) в UI
- ❌ Индикаторы онлайн-пользователей
- ❌ Уведомления о прочтении

### 10.10.4. План развития фронтенда

**Приоритет 1 (MVP+):**
1. Загрузка и отображение файлов
2. Удаление сообщений (для автора)
3. Поиск по сообщениям

**Приоритет 2:**
4. Добавление участников в чат (через поиск пользователей)
5. Удаление участников
6. Индикаторы онлайн-статуса

**Приоритет 3:**
7. Админ-панель
8. Push-уведомления (Android)
9. Оффлайн-режим (cache последних сообщений)
