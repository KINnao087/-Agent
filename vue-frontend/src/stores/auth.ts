import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  let expiryTimer: ReturnType<typeof setTimeout> | null = null

  const isLoggedIn = computed(() => {
    return !!token.value && !isTokenExpired(token.value)
  })

  async function login(email: string, password: string) {
    const res = await authApi.login(email, password)
    token.value = res.data.token
    user.value = { id: res.data.userId, username: res.data.username, email: res.data.email }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
    scheduleTokenExpiry(token.value)
  }

  function getTokenExpiresAt(token: string): number | null {
    try {
      const base64Url = token.split('.')[1]
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
      const padded = base64.padEnd(base64.length + (4 - base64.length % 4) % 4, '=')
      const payload = JSON.parse(atob(padded))
      return payload.exp ? payload.exp * 1000 : null
    } catch {
      return null
    }
  }

  function isTokenExpired(token: string): boolean {
    const expiresAt = getTokenExpiresAt(token)
    return !expiresAt || Date.now() >= expiresAt
  }

  function scheduleTokenExpiry(currentToken: string) {
    if (expiryTimer) {
      clearTimeout(expiryTimer)
      expiryTimer = null
    }

    const expiresAt = getTokenExpiresAt(currentToken)
    if (!expiresAt) {
      logout()
      return
    }

    const delay = expiresAt - Date.now()
    if (delay <= 0) {
      logout()
      if (window.location.pathname !== '/login') {
        window.location.replace('/login')
      }
      return
    }

    expiryTimer = setTimeout(() => {
      logout()
      if (window.location.pathname !== '/login') {
        window.location.replace('/login')
      }
    }, delay)
  }

  async function register(username: string, email: string, password: string) {
    const res = await authApi.register(username, email, password)
    token.value = res.data.token
    user.value = { id: res.data.userId, username: res.data.username, email: res.data.email }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
    scheduleTokenExpiry(token.value)
  }

  function logout() {
    if (expiryTimer) {
      clearTimeout(expiryTimer)
      expiryTimer = null
    }
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  if (token.value) {
    scheduleTokenExpiry(token.value)
  }

  return { token, user, isLoggedIn, login, register, logout, isTokenExpired }
})
