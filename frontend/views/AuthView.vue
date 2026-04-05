<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>💬 Messenger</h1>

      <div v-if="error" class="error-message">{{ error }}</div>

      <div v-if="isLogin">
        <div class="form-group">
          <label>Username</label>
          <input v-model="username" type="text" placeholder="Enter username" @keyup.enter="handleLogin" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="password" type="password" placeholder="Enter password" @keyup.enter="handleLogin" />
        </div>
        <button @click="handleLogin">Login</button>
        <div class="toggle-link">
          No account? <a @click="isLogin = false">Register with invite code</a>
        </div>
      </div>

      <div v-else>
        <div class="form-group">
          <label>Username</label>
          <input v-model="username" type="text" placeholder="Choose username" @keyup.enter="handleRegister" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="password" type="password" placeholder="Choose password" @keyup.enter="handleRegister" />
        </div>
        <div class="form-group">
          <label>Invite Code</label>
          <input v-model="inviteCode" type="text" placeholder="Enter invite code" @keyup.enter="handleRegister" />
        </div>
        <button @click="handleRegister">Register</button>
        <div class="toggle-link">
          Have an account? <a @click="isLogin = true">Login</a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const isLogin = ref(true)
const username = ref('')
const password = ref('')
const inviteCode = ref('')
const error = ref('')

async function handleLogin() {
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message
  }
}

async function handleRegister() {
  error.value = ''
  try {
    await auth.register(username.value, password.value, inviteCode.value)
    router.push('/')
  } catch (e) {
    error.value = e.message
  }
}
</script>