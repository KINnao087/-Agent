import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { appendDiagnosticLog } from '@/utils/diagnostics'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/RegisterView.vue'),
    },
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/contracts/upload',
      name: 'Upload',
      component: () => import('@/views/UploadView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/contracts/:id/review',
      name: 'Review',
      component: () => import('@/views/ReviewView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  if (to.meta.requiresAuth) {
    const auth = useAuthStore()
    if (!auth.token) {
      const details = {
        to: to.fullPath,
        currentPath: window.location.pathname,
      }
      console.warn('router guard redirecting to /login because token is missing', details)
      appendDiagnosticLog('warn', 'router.guard', 'missing_token_redirect', details)
      auth.logout('router_missing_token', {
        to: to.fullPath,
        currentPath: window.location.pathname,
      })
      next('/login')
      return
    }
  }
  next()
})

export default router
