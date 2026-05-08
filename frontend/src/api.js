export const API_SECRET_STORAGE_KEY = 'anam_api_secret'

export function getApiSecret() {
  try {
    return window.localStorage.getItem(API_SECRET_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

export function setApiSecret(secret) {
  const normalized = secret.trim()
  try {
    if (normalized) {
      window.localStorage.setItem(API_SECRET_STORAGE_KEY, normalized)
    } else {
      window.localStorage.removeItem(API_SECRET_STORAGE_KEY)
    }
  } catch {
    // localStorage may be unavailable in hardened/private browser contexts.
  }
}

export function clearApiSecret() {
  try {
    window.localStorage.removeItem(API_SECRET_STORAGE_KEY)
  } catch {
    // localStorage may be unavailable in hardened/private browser contexts.
  }
}

export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const secret = getApiSecret()
  if (secret) {
    headers.set('x-anam-secret', secret)
  }

  return fetch(path, {
    ...options,
    headers,
  })
}

export async function readErrorMessage(resp, fallback) {
  if (resp.status === 401) {
    return 'API secret required or invalid.'
  }

  const fallbackMessage = fallback || `HTTP ${resp.status} ${resp.statusText}`.trim()
  try {
    const contentType = resp.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      const data = await resp.json()
      const message = data?.detail || data?.message || data?.error
      return typeof message === 'string' ? message : JSON.stringify(message || data)
    }

    const text = await resp.text()
    return text.trim() || fallbackMessage
  } catch {
    return fallbackMessage
  }
}
