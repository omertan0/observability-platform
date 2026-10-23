import { lazy, Suspense, useState } from 'react'
import LogTable from './LogTable.jsx'
import AlertsPanel from './AlertsPanel.jsx'
import RulesPanel from './RulesPanel.jsx'
import { apiFetch } from './apiClient.js'

const MetricsPanel = lazy(() => import('./MetricsPanel.jsx'))

export default function App({ user, onLogout, signingOut = false }) {
  const [checking, setChecking] = useState(false)
  const [checks, setChecks] = useState(null)
  const [message, setMessage] = useState('Bağlantı henüz kontrol edilmedi.')
  const [lastChecked, setLastChecked] = useState(null)

  async function checkConnection() {
    setChecking(true)
    setChecks(null)
    setMessage('Servislerin yanıtı bekleniyor…')
    try {
      const response = await apiFetch('/api/ready', { signal: AbortSignal.timeout(15000) })
      const data = await response.json()
      if (typeof data.checks?.database !== 'boolean' || typeof data.checks?.redis !== 'boolean') {
        throw new Error('Beklenmeyen API yanıtı')
      }
      setChecks({ api: true, database: data.checks.database, redis: data.checks.redis })
      setMessage(response.ok ? 'API, veritabanı ve kuyruk erişilebilir.' : 'API yanıt verdi. Hazır olmayan servisleri kontrol et.')
    } catch {
      setChecks({ api: false })
      setMessage('API yanıtı alınamadı. FastAPI sunucusunun 8000 portunda çalıştığını kontrol et.')
    } finally {
      setLastChecked(new Date())
      setChecking(false)
    }
  }

  const services = [
    { key: 'api', name: 'Veri alım API’si', detail: 'FastAPI', number: '01' },
    { key: 'database', name: 'Veri depolama', detail: 'PostgreSQL · TimescaleDB', number: '02' },
    { key: 'redis', name: 'Görev kuyruğu', detail: 'Redis', number: '03' },
  ]

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Observability ana sayfa">
          <span className="brand-icon" aria-hidden="true">▥</span>
          <span>observability<span className="brand-dot">.</span></span>
        </a>
        <div className="session-tools">
          <span className="environment">{user || 'Yerel ortam'}</span>
          {onLogout && <button className="secondary-button" onClick={onLogout} disabled={signingOut}>{signingOut ? 'Çıkılıyor…' : 'Çıkış yap'}</button>}
        </div>
      </header>

      <main>
        <div className="page-heading">
          <div>
            <p className="eyebrow">GENEL BAKIŞ</p>
            <h1>Sistem durumu</h1>
            <p className="intro">İzleme platformunun servis bağlantılarını kontrol et.</p>
          </div>
          <button onClick={checkConnection} disabled={checking}>
            {checking ? 'Kontrol ediliyor…' : 'Bağlantıyı kontrol et'}
          </button>
        </div>

        <div className="connection-summary" role="status">
          <p className={`connection-message ${checks?.api === false ? 'connection-error' : ''}`}>{message}</p>
          {lastChecked && !checking && (
            <time dateTime={lastChecked.toISOString()}>
              Son kontrol: {lastChecked.toLocaleTimeString('tr-TR')}
            </time>
          )}
        </div>

        <section className="service-grid" aria-label="Servis bağlantıları" aria-busy={checking}>
          {services.map((service) => {
            const ready = checks?.[service.key]
            const statusText = checking ? 'Kontrol ediliyor…'
              : ready === true ? 'Erişilebilir'
              : ready === false ? 'Hazır değil'
              : checks === null ? 'Kontrol bekliyor' : 'Kontrol edilemedi'
            return (
              <article className="service-card" key={service.key}>
                <div className="card-heading">
                  <span className="card-number">{service.number}</span>
                  <span className={`status ${ready === undefined ? '' : ready ? 'ready' : 'unavailable'}`}>
                    {statusText}
                  </span>
                </div>
                <h2>{service.name}</h2>
                <p>{service.detail}</p>
              </article>
            )
          })}
        </section>

        <Suspense fallback={<section className="logs-panel"><p className="logs-feedback" role="status">Metrik grafiği hazırlanıyor…</p></section>}>
          <MetricsPanel />
        </Suspense>
        <LogTable />
        <AlertsPanel />
        <RulesPanel />

        <section className="workflow" aria-labelledby="workflow-title">
          <p className="eyebrow">VERİ AKIŞI</p>
          <h2 id="workflow-title">Kayıttan bildirime</h2>
          <p>Uygulama <span aria-hidden="true">→</span> API <span aria-hidden="true">→</span> Kuyruk <span aria-hidden="true">→</span> Worker <span aria-hidden="true">→</span> Veritabanı <span aria-hidden="true">→</span> Alarm</p>
          <small>Bu kontrol API, veritabanı ve Redis bağlantısını ölçer. Worker’ın görev işleyebildiğini ayrıca doğrulamak gerekir.</small>
        </section>
      </main>
    </div>
  )
}
