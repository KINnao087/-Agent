const STORAGE_KEY = 'contract_review_debug_logs'
const MAX_LOGS = 200

export interface DiagnosticEntry {
  ts: string
  level: 'info' | 'warn' | 'error'
  source: string
  event: string
  data: unknown
}

function safeRead(): DiagnosticEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function safeWrite(entries: DiagnosticEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Ignore storage failures.
  }
}

export function appendDiagnosticLog(
  level: DiagnosticEntry['level'],
  source: string,
  event: string,
  data: unknown,
) {
  const next = safeRead()
  next.push({
    ts: new Date().toISOString(),
    level,
    source,
    event,
    data,
  })
  if (next.length > MAX_LOGS) {
    next.splice(0, next.length - MAX_LOGS)
  }
  safeWrite(next)
}

export function readDiagnosticLogs(): DiagnosticEntry[] {
  return safeRead()
}

export function clearDiagnosticLogs() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore storage failures.
  }
}

declare global {
  interface Window {
    __contractReviewDiagnostics?: {
      read: typeof readDiagnosticLogs
      clear: typeof clearDiagnosticLogs
    }
  }
}

if (typeof window !== 'undefined') {
  window.__contractReviewDiagnostics = {
    read: readDiagnosticLogs,
    clear: clearDiagnosticLogs,
  }
}
