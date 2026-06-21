<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from './stores/auth'
import { useRouter, useRoute } from 'vue-router'
import { appendDiagnosticLog } from '@/utils/diagnostics'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// ===== 主题管理 =====
const isDark = ref(false)

function initTheme() {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark') {
    isDark.value = true
  } else if (saved === 'light') {
    isDark.value = false
  } else {
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme()
}

function applyTheme() {
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme()
}

onMounted(initTheme)

// ===== 设置弹窗 =====
const showSettings = ref(false)

function openSettings() {
  showSettings.value = true
}

function closeSettings() {
  showSettings.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && showSettings.value) {
    closeSettings()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

// ===== 登出 =====
function logout() {
  console.info('User initiated logout')
  appendDiagnosticLog('info', 'app', 'user_click_logout', {
    currentPath: window.location.pathname,
  })
  auth.logout('user_click')
  router.push('/login')
}

// ===== 侧边栏导航项 =====
const navItems = [
  { path: '/dashboard',        label: '工作台',   icon: '📊' },
  { path: '/contracts/upload', label: '上传合同', icon: '📤' },
]
</script>

<template>
  <!-- 未登录 -->
  <div v-if="!auth.isLoggedIn">
    <router-view />
  </div>

  <!-- 已登录 -->
  <div v-else class="app-layout">
    <!-- ====== 侧边栏 ====== -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="sidebar-logo-icon">📋</div>
        <span class="sidebar-logo-text">合同审核</span>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="sidebar-item"
          :class="{ active: route.path === item.path }"
        >
          <span class="sidebar-item-icon">{{ item.icon }}</span>
          <span class="sidebar-item-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <!-- 用户信息 — 点击弹出设置 -->
        <button class="sidebar-user-btn" @click="openSettings">
          <div class="sidebar-user-avatar">
            {{ auth.user?.username?.charAt(0)?.toUpperCase() }}
          </div>
          <span class="sidebar-user-name">{{ auth.user?.username }}</span>
          <span class="sidebar-user-caret">▾</span>
        </button>

        <button class="sidebar-logout-btn" @click="logout">
          <span>🚪</span>
          <span>退出登录</span>
        </button>
      </div>
    </aside>

    <!-- ====== 主内容区 ====== -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- ====== 设置弹窗 ====== -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="showSettings" class="modal-overlay" @click.self="closeSettings">
          <div class="modal-card">
            <div class="modal-header">
              <h3>页面设置</h3>
              <button class="modal-close" @click="closeSettings">✕</button>
            </div>

            <div class="modal-body">
              <!-- 主题切换 -->
              <button class="modal-setting-item" @click="toggleTheme">
                <div class="modal-setting-icon">
                  {{ isDark ? '🌙' : '☀️' }}
                </div>
                <div class="modal-setting-info">
                  <div class="modal-setting-label">主题模式</div>
                  <div class="modal-setting-desc">
                    {{ isDark ? '当前：深色模式' : '当前：浅色模式' }}
                  </div>
                </div>
                <div class="modal-setting-arrow">→</div>
              </button>

              <!-- 预留更多设置项 -->
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style>
/* ===== 模态框过渡动画 ===== */
.modal-enter-active { transition: all 0.25s ease; }
.modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from,
.modal-leave-to { opacity: 0; }
.modal-enter-from .modal-card,
.modal-leave-to .modal-card {
  transform: scale(0.92) translateY(20px);
}
</style>

<style scoped>
/* ===== 模态框 ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.modal-card {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  width: 400px;
  max-width: calc(100vw - 48px);
  overflow: hidden;
  transition: transform 0.25s ease;
}

/* 头部 */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 14px;
}

.modal-header h3 {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.2px;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.modal-close:hover { background: var(--bg-hover); color: var(--text-primary); }

/* 内容 */
.modal-body {
  padding: 0 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 设置项 */
.modal-setting-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 14px 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: all 0.15s ease;
}
.modal-setting-item:hover { background: var(--bg-hover); }

.modal-setting-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.modal-setting-info { flex: 1; }

.modal-setting-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.modal-setting-desc {
  font-size: 12px;
  color: var(--text-tertiary);
}

.modal-setting-arrow {
  font-size: 14px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
</style>
