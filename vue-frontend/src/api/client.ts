import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { appendDiagnosticLog } from '@/utils/diagnostics'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  if (config.url?.includes('/report/markdown')) {
    const details = {
      method: config.method ?? null,
      url: config.url,
      baseURL: config.baseURL ?? null,
      hasToken: !!auth.token,
      authHeaderSet: !!config.headers?.Authorization,
      currentPath: window.location.pathname,
    }
    console.info('API request markdown', details)
    appendDiagnosticLog('info', 'api.client', 'markdown_request', details)
  }
  return config
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const details = {
      status: err.response?.status ?? null,
      method: err.config?.method ?? null,
      url: err.config?.url ?? null,
      baseURL: err.config?.baseURL ?? null,
      message: err.message ?? null,
      data: err.response?.data ?? null,
    }

    if (err.response?.status === 401) {
      console.error('API 401 -> logout', details)
      appendDiagnosticLog('error', 'api.client', 'api_401', details)
      const auth = useAuthStore()
      auth.logout('api_401', details)
      window.location.href = '/login'
    } else {
      console.warn('API error', details)
      appendDiagnosticLog('warn', 'api.client', 'api_error', details)
    }
    return Promise.reject(err)
  },
)

export default client
