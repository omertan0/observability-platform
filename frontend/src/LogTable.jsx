import { useEffect, useState } from 'react'

const timeFormatter = new Intl.DateTimeFormat('tr-TR', {
  dateStyle: 'short',
  timeStyle: 'medium',
})

function formatTime(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Geçersiz zaman' : timeFormatter.format(date)
}

export default function LogTable() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = setTimeout(() => controller.abort(), 15000)

    async function loadLogs() {
      setLoading(true)
      setError('')
      try {
        const response = await fetch('/api/logs?limit=20', { signal: controller.signal })
        if (!response.ok) {
          throw new Error(response.status === 503
            ? 'Veritabanına şu anda erişilemiyor. Servisleri kontrol edip yeniden dene.'
            : `Loglar alınamadı (HTTP ${response.status}). Yeniden dene.`)
        }
        const data = await response.json()
        if (!Array.isArray(data.items)) {
          throw new Error('API beklenen log listesini döndürmedi.')
        }
        if (active) {
          setLogs(data.items)
          setLastUpdated(new Date())
        }
      } catch (cause) {
        if (active) {
          setError(controller.signal.aborted
            ? 'Log isteği zaman aşımına uğradı. Yeniden dene.'
            : cause instanceof Error ? cause.message : 'Loglar yüklenemedi. Yeniden dene.')
        }
      } finally {
        clearTimeout(timeout)
        if (active) setLoading(false)
      }
    }

    loadLogs()
    return () => {
      active = false
      clearTimeout(timeout)
      controller.abort()
    }
  }, [refreshKey])

  return (
    <section className="logs-panel" aria-labelledby="logs-title" aria-busy={loading}>
      <div className="logs-heading">
        <div>
          <p className="eyebrow">OLAY KAYITLARI</p>
          <h2 id="logs-title">Son loglar</h2>
          <p className="logs-description">Olay zamanına göre en yeni 20 kayıt. Saatler tarayıcının yerel saatine göre gösterilir.</p>
        </div>
        <button className="secondary-button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}>
          {loading ? 'Yükleniyor…' : 'Logları yenile'}
        </button>
      </div>

      {loading && <p className="logs-feedback" role="status">Loglar yükleniyor…</p>}
      {!loading && error && <p className="logs-feedback connection-error" role="alert">{error}</p>}
      {!loading && !error && logs.length === 0 && (
        <p className="logs-feedback" role="status">Henüz log kaydı yok. API’ye bir log gönderdikten sonra “Logları yenile” düğmesine bas.</p>
      )}
      {!loading && !error && logs.length > 0 && (
        <>
          <div className="logs-scroll" role="region" aria-label="Log tablosu" tabIndex={0}>
            <table className="logs-table">
              <caption className="sr-only">Zaman, servis, seviye ve mesaj bilgileriyle son log kayıtları</caption>
              <thead>
                <tr><th scope="col">Zaman</th><th scope="col">Servis</th><th scope="col">Seviye</th><th scope="col">Mesaj</th></tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={`${log.timestamp}-${log.id}`}>
                    <td className="log-time"><time dateTime={log.timestamp}>{formatTime(log.timestamp)}</time></td>
                    <td className="log-service">{log.service}</td>
                    <td><span className={`log-level level-${log.level}`}>{log.level}</span></td>
                    <td className="log-message">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="logs-footer" role="status">
            {logs.length} kayıt gösteriliyor.
            {lastUpdated && <> Son güncelleme: <time dateTime={lastUpdated.toISOString()}>{lastUpdated.toLocaleTimeString('tr-TR')}</time></>}
          </p>
        </>
      )}
    </section>
  )
}
