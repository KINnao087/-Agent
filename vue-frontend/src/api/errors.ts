export interface ApiErrorBody {
  status?: number
  code?: string
  message?: string
  path?: string
  details?: unknown
}

const FORCE_LOGOUT_ERROR_CODES = new Set([
  'AUTHENTICATION_REQUIRED',
  'AUTHENTICATION_INVALID_TOKEN',
  'AUTHENTICATION_TOKEN_EXPIRED',
  'AUTHENTICATION_USER_NOT_FOUND',
])

function asObject(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

export function getApiErrorBody(error: unknown): ApiErrorBody | null {
  const errorObject = asObject(error)
  const response = asObject(errorObject?.response)
  const data = asObject(response?.data)
  if (!data) return null

  return {
    status: typeof data.status === 'number' ? data.status : undefined,
    code: typeof data.code === 'string' ? data.code : undefined,
    message: typeof data.message === 'string' ? data.message : undefined,
    path: typeof data.path === 'string' ? data.path : undefined,
    details: data.details,
  }
}

export function extractApiErrorCode(error: unknown): string | null {
  return getApiErrorBody(error)?.code ?? null
}

export function extractApiErrorMessage(error: unknown, fallback: string): string {
  const apiBody = getApiErrorBody(error)
  if (apiBody?.message) return apiBody.message

  const errorObject = asObject(error)
  if (typeof errorObject?.message === 'string' && errorObject.message) {
    return errorObject.message
  }

  return fallback
}

export function isAuthRequest(error: unknown): boolean {
  const errorObject = asObject(error)
  const config = asObject(errorObject?.config)
  const url = typeof config?.url === 'string' ? config.url : ''
  return url.startsWith('/auth/')
}

export function shouldForceLogout(error: unknown): boolean {
  const errorObject = asObject(error)
  const response = asObject(errorObject?.response)
  const status = typeof response?.status === 'number' ? response.status : null
  const code = extractApiErrorCode(error)
  return status === 401 && !!code && FORCE_LOGOUT_ERROR_CODES.has(code)
}
