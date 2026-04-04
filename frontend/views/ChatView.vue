<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <div class="sidebar" :class="{ hidden: !showSidebar }">
      <div class="sidebar-header">
        <h2>💬 Chats</h2>
        <div>
          <button class="theme-toggle" @click="toggleTheme">{{ theme === 'dark' ? '☀️' : '🌙' }}</button>
          <button @click="showCreateChat = true">+</button>
        </div>
      </div>

      <div class="chat-list">
        <div
          v-for="chat in chatStore.chats"
          :key="chat.id"
          class="chat-item"
          :class="{ active: chatStore.currentChat?.id === chat.id }"
          @click="selectChat(chat)"
        >
          <div class="chat-name">{{ chat.name || 'Personal Chat' }}</div>
          <div class="last-message">{{ chat.type }}</div>
        </div>
      </div>

      <div class="user-menu">
        <div class="username">{{ auth.user?.username || 'User' }}</div>
        <button @click="showProfile = true">Profile</button>
        <button @click="handleLogout" style="margin-top: 5px; background: var(--error)">Logout</button>
      </div>
    </div>

    <!-- Chat Window -->
    <div class="chat-window">
      <div v-if="chatStore.currentChat" class="chat-header">
        <button v-if="!showSidebar" @click="showSidebar = true" style="margin-right: 10px">☰</button>
        <strong>{{ chatStore.currentChat.name || 'Personal Chat' }}</strong>
        <span style="color: var(--text-secondary); font-size: 13px; margin-left: 10px">
          {{ chatStore.members.length }} members
        </span>
      </div>

      <div v-if="chatStore.currentChat" class="messages-container" ref="messagesContainer">
        <div v-if="chatStore.hasMore && !chatStore.loading" style="text-align: center; padding: 10px">
          <button @click="loadMore" style="background: var(--bg-tertiary)">Load more</button>
        </div>
        <div v-if="chatStore.loading" style="text-align: center; padding: 10px">Loading...</div>

        <div
          v-for="msg in chatStore.messages"
          :key="msg.id"
          class="message"
          :class="{ own: msg.sender_id === auth.user?.id, other: msg.sender_id !== auth.user?.id }"
        >
          <div class="sender">{{ msg.sender_username }}</div>
          <div class="content">{{ msg.content }}</div>
          <div class="time">{{ formatTime(msg.created_at) }}</div>
        </div>
      </div>

      <div v-else class="no-chat-selected">
        <div>Select a chat or create a new one</div>
      </div>

      <div v-if="chatStore.currentChat" class="message-input">
        <input
          v-model="newMessage"
          placeholder="Type a message..."
          @keyup.enter="sendMessage"
        />
        <button @click="sendMessage">Send</button>
      </div>
    </div>

    <!-- Create Chat Modal -->
    <div v-if="showCreateChat" class="modal-overlay" @click.self="showCreateChat = false">
      <div class="modal">
        <h3>Create Chat</h3>
        <div class="form-group">
          <label>Name (optional for group)</label>
          <input v-model="newChatName" placeholder="Chat name" />
        </div>
        <div class="form-group">
          <label>Type</label>
          <select v-model="newChatType">
            <option value="group">Group</option>
            <option value="personal">Personal</option>
          </select>
        </div>
        <button @click="createChat">Create</button>
        <button @click="showCreateChat = false" style="background: var(--bg-tertiary); margin-top: 5px">Cancel</button>
      </div>
    </div>

    <!-- Profile Modal -->
    <div v-if="showProfile" class="modal-overlay" @click.self="showProfile = false">
      <div class="modal">
        <h3>Profile</h3>
        <div class="form-group">
          <label>Username</label>
          <input v-model="profileUsername" />
        </div>
        <div class="form-group" v-if="inviteCodeResult">
          <label>Your invite code</label>
          <input :value="inviteCodeResult" readonly />
        </div>
        <button @click="updateProfile">Save</button>
        <button @click="generateInvite" style="margin-top: 5px; background: var(--success)">Generate Invite</button>
        <button @click="showProfile = false" style="background: var(--bg-tertiary); margin-top: 5px">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const auth = useAuthStore()
const chatStore = useChatStore()

const newMessage = ref('')
const showSidebar = ref(true)
const showCreateChat = ref(false)
const showProfile = ref(false)
const newChatName = ref('')
const newChatType = ref('group')
const profileUsername = ref(auth.user?.username || '')
const inviteCodeResult = ref('')
const messagesContainer = ref(null)

const theme = ref(localStorage.getItem('theme') || 'dark')
document.documentElement.setAttribute('data-theme', theme.value)

let ws = null

onMounted(async () => {
  if (!auth.token) {
    router.push('/auth')
    return
  }
  await chatStore.fetchChats(auth.token)
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) ws.close()
})

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem('theme', theme.value)
  document.documentElement.setAttribute('data-theme', theme.value)
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${window.location.host}/ws?token=${auth.token}`)

  ws.onopen = () => {
    console.log('WebSocket connected')
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

  ws.onerror = (err) => console.error('WebSocket error:', err)
  ws.onclose = () => {
    console.log('WebSocket closed, reconnecting...')
    setTimeout(connectWebSocket, 3000)
  }
}

async function selectChat(chat) {
  await chatStore.selectChat(chat.id, auth.token)
  if (ws) {
    ws.send(JSON.stringify({ action: 'subscribe', chat_id: chat.id }))
  }
  showSidebar.value = window.innerWidth > 768
  scrollToBottom()
}

async function sendMessage() {
  if (!newMessage.value.trim()) return
  await chatStore.sendMessage(newMessage.value, auth.token)
  newMessage.value = ''
  scrollToBottom()
}

async function loadMore() {
  await chatStore.fetchMessages(auth.token)
}

async function createChat() {
  await chatStore.createChat({
    type: newChatType.value,
    name: newChatName.value || null,
    member_ids: []
  }, auth.token)
  showCreateChat.value = false
  newChatName.value = ''
}

async function updateProfile() {
  try {
    await auth.updateProfile(profileUsername.value)
    showProfile.value = false
  } catch (e) {
    alert(e.message)
  }
}

async function generateInvite() {
  try {
    inviteCodeResult.value = await auth.generateInvite()
  } catch (e) {
    alert(e.message)
  }
}

function handleLogout() {
  auth.logout()
  chatStore.reset()
  if (ws) ws.close()
  router.push('/auth')
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// Watch for new messages to auto-scroll
watch(() => chatStore.messages.length, () => scrollToBottom())
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}

.modal {
  background: var(--bg-secondary);
  padding: 25px;
  border-radius: 12px;
  width: 90%;
  max-width: 400px;
}

.modal h3 {
  margin-bottom: 15px;
}

.modal .form-group {
  margin-bottom: 15px;
}

.modal label {
  display: block;
  margin-bottom: 5px;
  color: var(--text-secondary);
  font-size: 13px;
}

.modal input, .modal select {
  width: 100%;
}

.modal button {
  width: 100%;
  margin-top: 5px;
}

select {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 10px 15px;
  border-radius: 8px;
  font-size: 14px;
}
</style>