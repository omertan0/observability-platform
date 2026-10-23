// Oturum çerezi HttpOnly'dir; JavaScript yalnızca CSRF değerini bellekte tutar.
let csrfToken = null
export const SESSION_EXPIRED = 'observability:session-expired'

export function validateSession(data) {
  if (!data || typeof data.username !== 'string' || !data.username || data.username.length > 64
    || typeof data.csrf_token !== 'string' || !/^[A-Za-z0-9_-]{32,128}$/.test(data.csrf_token)
    || typeof data.expires_at !== 'string' || !Number.isFinite(Date.parse(data.expires_at))) {
    throw new Error('Oturum yanıtı doğrulanamadı.')
  }
  return data
}

export function setSession(data) {
  csrfToken = data ? validateSession(data).csrf_token : null
}

export function notifySessionExpired() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(SESSION_EXPIRED))
}

export async function apiFetch(url, options = {}, transport = fetch) {
  if (typeof url !== 'string' || !url.startsWith('/api/') || url.includes('\\')) {
    throw new Error('Yalnızca panelin API adresi kullanılabilir.')
  }
  const headers = new Headers(options.headers)
  const method = (options.method || 'GET').toUpperCase()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  const response = await transport(url, { ...options, headers, credentials: 'same-origin', redirect: 'error' })
  if (response.status === 401) notifySessionExpired()
  return response
}
