import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  async function login(email: string, password: string) {
    const res = await authApi.login(email, password)
    token.value = res.data.token
    user.value = { id: res.data.userId, username: res.data.username, email: res.data.email }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  async function register(username: string, email: string, password: string) {
    const res = await authApi.register(username, email, password)
    token.value = res.data.token
    user.value = { id: res.data.userId, username: res.data.username, email: res.data.email }
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, login, register, logout }
})
