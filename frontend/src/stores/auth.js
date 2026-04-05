import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = '/messenger/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(username, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      credentials: 'include'
    })
    if (!res.ok) throw new Error('Invalid credentials')
    const data = await res.json()
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchMe()
  }

  async function register(username, password, inviteCode) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, invite_code: inviteCode }),
      credentials: 'include'
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Registration failed')
    }
    const data = await res.json()
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchMe()
  }

  async function fetchMe() {
    if (!token.value) return
    const res = await fetch(`${API_BASE}/auth/me`, {
      credentials: 'include',
      headers: { 'Authorization': `Bearer ${token.value}` }
    })
    if (res.ok) {
      user.value = await res.json()
    } else {
      logout()
    }
  }

  async function updateProfile(username) {
    const res = await fetch(`${API_BASE}/auth/me`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token.value}`
      },
      body: JSON.stringify({ username })
    })
    if (!res.ok) throw new Error('Update failed')
    user.value = await res.json()
  }

  async function generateInvite() {
    const res = await fetch(`${API_BASE}/auth/invite`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token.value}` }
    })
    if (!res.ok) throw new Error('Failed to generate invite')
    return (await res.json()).code
  }

  async function searchUsers(query, limit = 20) {
    const res = await fetch(`${API_BASE}/users/search?q=${encodeURIComponent(query)}&limit=${limit}`, {
      headers: { 'Authorization': `Bearer ${token.value}` }
    })
    if (!res.ok) throw new Error('Search failed')
    return await res.json()
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { user, token, isAuthenticated, login, register, fetchMe, updateProfile, generateInvite, searchUsers, logout }
})