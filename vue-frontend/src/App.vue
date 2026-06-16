<script setup lang="ts">
import { useAuthStore } from './stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div>
    <nav v-if="auth.isLoggedIn" class="navbar">
      <div class="logo">📋 合同审核平台</div>
      <div class="nav-right">
        <router-link to="/dashboard">工作台</router-link>
        <router-link to="/contracts/upload">上传合同</router-link>
        <span>{{ auth.user?.username }}</span>
        <button class="btn btn-default" @click="logout">退出</button>
      </div>
    </nav>
    <router-view />
  </div>
</template>
