import { useEffect, useRef, useState } from 'react'
import App from './App.jsx'
import { apiFetch, SESSION_EXPIRED, setSession, validateSession } from './apiClient.js'

export default function AuthGate() {
  const [session, updateSession] = useState(null)
  const [checking, setChecking] = useState(true)
  const [busy, setBusy] = useState(false)
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [retry, setRetry] = useState(0)
  const requestRef = useRef(null)

  function acceptSession(data) {
    const validated = validateSession(data)
    setSession(validated)
    updateSession(validated)
    setPassword('')
    setMessage('')
  }

  function expireSession() {
    setSession(null)
    updateSession(null)
    setPassword('')
    setMessage('Oturum sona erdi. Yeniden giriş yap.')
  }

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED, expireSession)
    return () => window.removeEventListener(SESSION_EXPIRED, expireSession)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = setTimeout(() => controller.abort(), 15000)
    setChecking(true)
    async function restore() {
      try {
        const response = await fetch('/api/auth/session', { signal: controller.signal, credentials: 'same-origin', redirect: 'error' })
        if (!active) return
        if (response.status === 401) { setSession(null); updateSession(null); setMessage(''); return }
        if (!response.ok) throw new Error('Oturum kontrol edilemedi. Servisleri kontrol edip yeniden dene.')
        const data = await response.json()
        if (active) acceptSession(data)
      } catch (error) {
        if (active) setMessage(controller.signal.aborted ? 'Oturum kontrolü zaman aşımına uğradı. Yeniden dene.' : error.message)
      } finally {
        clearTimeout(timeout)
        if (active) setChecking(false)
      }
    }
    restore()
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [retry])

  useEffect(() => {
    if (!session) return
    const timeout = setTimeout(expireSession, Math.max(0, Date.parse(session.expires_at) - Date.now()))
    return () => clearTimeout(timeout)
  }, [session])

  useEffect(() => () => { requestRef.current?.abort() }, [])

  async function submit(event) {
    event.preventDefault()
    if (requestRef.current) return
    const controller = new AbortController()
    requestRef.current = controller
    const timeout = setTimeout(() => controller.abort(), 15000)
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST', credentials: 'same-origin', redirect: 'error', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'observability' },
        body: JSON.stringify({ username, password }),
      })
      if (!response.ok) throw new Error(response.status === 401 ? 'Kullanıcı adı veya şifre yanlış.'
        : response.status === 429 ? 'Çok fazla deneme yapıldı. Bir dakika sonra yeniden dene.'
          : response.status === 503 ? 'Giriş servisi hazır değil. Sunucu ayarlarını ve Redis bağlantısını kontrol et.'
            : 'Giriş tamamlanamadı. Bilgilerini kontrol edip yeniden dene.')
      const data = await response.json()
      if (requestRef.current === controller) acceptSession(data)
    } catch (error) {
      if (requestRef.current === controller) {
        setPassword('')
        setMessage(controller.signal.aborted ? 'Giriş isteği zaman aşımına uğradı. Oturumu kontrol edebilirsin.'
          : error instanceof TypeError ? 'Sunucuya erişilemiyor. Bağlantını kontrol edip yeniden dene.' : error.message)
      }
    } finally {
      clearTimeout(timeout)
      if (requestRef.current === controller) { requestRef.current = null; setBusy(false) }
    }
  }

  async function logout() {
    if (requestRef.current) return
    const controller = new AbortController()
    requestRef.current = controller
    const timeout = setTimeout(() => controller.abort(), 15000)
    setBusy(true)
    setMessage('')
    try {
      const response = await apiFetch('/api/auth/logout', { method: 'POST', signal: controller.signal })
      if (response.status !== 401 && (!response.ok || (await response.json()).status !== 'signed_out')) throw new Error()
      setSession(null)
      updateSession(null)
      setPassword('')
      setMessage('Çıkış yapıldı.')
    } catch {
      setMessage('Çıkış doğrulanamadı. Yeniden dene.')
    } finally {
      clearTimeout(timeout)
      requestRef.current = null
      setBusy(false)
    }
  }

  if (session && !checking) return <>
    {message && <p className="session-notice" role="alert">{message}</p>}
    <App user={session.username} onLogout={logout} signingOut={busy} />
  </>

  return <div className="auth-shell">
    <main className="auth-card" aria-busy={checking || busy}>
      <p className="eyebrow">OBSERVABILITY PLATFORM</p>
      <h1>Panele giriş</h1>
      <p className="intro">Servislerini izle, kayıtları incele ve alarm kurallarını yönet.</p>
      {checking ? <p role="status">Oturum kontrol ediliyor…</p> : <form onSubmit={submit} className="auth-form">
        <label htmlFor="login-user">Kullanıcı adı
          <input id="login-user" autoComplete="username" required maxLength={64} value={username}
            disabled={busy} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label htmlFor="login-password">Şifre
          <input id="login-password" type="password" autoComplete="current-password" required maxLength={256}
            value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button disabled={busy} type="submit">{busy ? 'Giriş yapılıyor…' : 'Giriş yap'}</button>
      </form>}
      {message && <p className="filter-error" role="alert">{message}</p>}
      {!checking && <button className="secondary-button auth-retry" disabled={busy} onClick={() => setRetry((value) => value + 1)}>Oturumu kontrol et</button>}
    </main>
  </div>
}
