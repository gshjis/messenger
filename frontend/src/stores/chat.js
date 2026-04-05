import { defineStore } from 'pinia'
import { ref } from 'vue'

const API_BASE = '/messenger/api'

export const useChatStore = defineStore('chat', () => {
  const chats = ref([])
  const currentChat = ref(null)
  const messages = ref([])
  const members = ref([])
  const loading = ref(false)
  const page = ref(1)
  const hasMore = ref(true)

  async function fetchChats(token) {
    const res = await fetch(`${API_BASE}/chats`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (res.ok) chats.value = await res.json()
  }

  async function createChat(data, token) {
    const res = await fetch(`${API_BASE}/chats`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    })
    if (res.ok) {
      const chat = await res.json()
      chats.value.unshift(chat)
      return chat
    }
    throw new Error('Failed to create chat')
  }

  async function createOrGetPersonalChat(userId, token) {
    const res = await fetch(`${API_BASE}/chats/personal`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ user_id: userId })
    })
    if (res.ok) {
      const chat = await res.json()
      // Добавляем в список если ещё нет
      if (!chats.value.find(c => c.id === chat.id)) {
        chats.value.unshift(chat)
      }
      return chat
    }
    throw new Error('Failed to create personal chat')
  }

  async function selectChat(chatId, token) {
    currentChat.value = chats.value.find(c => c.id === chatId)
    messages.value = []
    page.value = 1
    hasMore.value = true
    await fetchMessages(token)
    await fetchMembers(token)
  }

  async function fetchMessages(token) {
    if (!currentChat.value || !hasMore.value) return
    loading.value = true
    try {
      const res = await fetch(
        `${API_BASE}/chats/${currentChat.value.id}/messages?page=${page.value}&per_page=50`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      )
      if (res.ok) {
        const data = await res.json()
        messages.value = [...messages.value, ...data.messages].sort((a, b) =>
          new Date(a.created_at) - new Date(b.created_at)
        )
        hasMore.value = data.has_next
        page.value++
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchMembers(token) {
    if (!currentChat.value) return
    const res = await fetch(`${API_BASE}/chats/${currentChat.value.id}/members`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (res.ok) members.value = await res.json()
  }

  async function sendMessage(content, token) {
    if (!currentChat.value) return
    const res = await fetch(`${API_BASE}/chats/${currentChat.value.id}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ content })
    })
    if (res.ok) {
      const msg = await res.json()
      messages.value.push(msg)
    }
  }

  function addMessage(msg) {
    messages.value.push(msg)
  }

  function reset() {
    chats.value = []
    currentChat.value = null
    messages.value = []
    members.value = []
    page.value = 1
    hasMore.value = true
  }

  return {
    chats, currentChat, messages, members, loading, page, hasMore,
    fetchChats, createChat, createOrGetPersonalChat, selectChat, fetchMessages, fetchMembers,
    sendMessage, addMessage, reset
  }
})