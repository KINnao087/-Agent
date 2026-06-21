import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import { appendDiagnosticLog } from '@/utils/diagnostics'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => {
    return !!token.value
  })

  async function login(email: string, password: string) {
    const res = await authApi.login(email, password)
    token.value = res.data.token
    user.value = { id: res.data.userId, username: res.data.username, email: res.data.email }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
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

  async function register(username: string, email: string, password: string) {
    const res = await authApi.register(username, email, password)
    token.value = res.data.token
    user.value = { id: res.data.userId, username: res.data.username, email: res.data.email }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  function logout(reason = 'unknown', meta?: unknown) {
    const details = {
      reason,
      meta,
      hasToken: !!token.value,
      userId: user.value?.id ?? null,
      currentPath: window.location.pathname,
      stack: new Error().stack,
    }
    console.warn('auth.logout called', details)
    appendDiagnosticLog('warn', 'auth.store', 'logout', details)
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, login, register, logout, isTokenExpired }
})
