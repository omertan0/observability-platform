import { useEffect, useRef, useState } from 'react'
import LogFilters from './LogFilters.jsx'
import LogDetails from './LogDetails.jsx'
import { apiFetch, notifySessionExpired } from './apiClient.js'
import { buildLogFilters, buildLogPageQuery, EMPTY_FILTERS, MAX_OFFSET, PAGE_SIZE } from './logQuery.js'

const EMPTY_RESULT = {
  query: null, items: [], loading: true, error: '',
  hasMore: false, nextOffset: null, lastUpdated: null,
}

const timeFormatter = new Intl.DateTimeFormat('tr-TR', {
  dateStyle: 'short',
  timeStyle: 'medium',
})

function formatTime(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Geçersiz zaman' : timeFormatter.format(date)
}

export default function LogTable() {
  const [draftFilters, setDraftFilters] = useState({ ...EMPTY_FILTERS })
  const [filterDirty, setFilterDirty] = useState(false)
  const [formError, setFormError] = useState('')
  const [view, setView] = useState({ filters: '', offset: 0 })
  const [result, setResult] = useState(EMPTY_RESULT)
  const [refreshKey, setRefreshKey] = useState(0)
  const [streamStatus, setStreamStatus] = useState('connecting')
  const [selectedLog, setSelectedLog] = useState(null)
  const detailOpenerRef = useRef(null)
  const headingRef = useRef(null)
  const pageQuery = buildLogPageQuery(view.filters, view.offset)
  // Başka filtreye/sayfaya ait yanıtı yeni görünümde göstermeyiz.
  const { items: logs, loading, error, hasMore, nextOffset, lastUpdated } = result.query === pageQuery ? result : EMPTY_RESULT

  useEffect(() => {
    if (view.offset > 0) {
      setStreamStatus('paused')
      return
    }
    if (!('EventSource' in window)) {
      setStreamStatus('unsupported')
      return
    }
    let active = true
    setStreamStatus('connecting')
    const stream = new EventSource('/api/stream/logs' + (view.filters ? `?${view.filters}` : ''))
    stream.onopen = () => { if (active) setStreamStatus('connecting') }
    stream.addEventListener('logs_changed', () => {
      if (!active) return
      setStreamStatus('live')
      setRefreshKey((value) => value + 1)
    })
    stream.addEventListener('stream_status', () => { if (active) setStreamStatus('unavailable') })
    stream.addEventListener('auth_expired', () => { if (active) { stream.close(); notifySessionExpired() } })
    stream.onerror = () => {
      if (active) setStreamStatus(stream.readyState === EventSource.CLOSED ? 'closed' : 'reconnecting')
    }
    return () => {
      active = false
      stream.close()
    }
  }, [view.filters, view.offset])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = setTimeout(() => controller.abort(), 15000)

    async function loadLogs() {
      setResult((previous) => ({
        ...(previous.query === pageQuery ? previous : EMPTY_RESULT),
        query: pageQuery, loading: true, error: '',
      }))
      try {
        const response = await apiFetch(`/api/logs?${pageQuery}`, { signal: controller.signal })
        if (!response.ok) {
          throw new Error(response.status === 503
            ? 'Veritabanına şu anda erişilemiyor. Servisleri kontrol edip yeniden dene.'
            : response.status === 422 ? 'Filtre değerleri geçersiz. Alanları kontrol edip yeniden uygula.'
            : `Loglar alınamadı (HTTP ${response.status}). Yeniden dene.`)
        }
        const data = await response.json()
        if (!Array.isArray(data.items) || typeof data.has_more !== 'boolean'
          || data.offset !== view.offset || data.limit !== PAGE_SIZE
          || (data.has_more && data.next_offset !== view.offset + PAGE_SIZE)) {
          throw new Error('API beklenen log listesini döndürmedi.')
        }
        if (active) {
          setResult({ query: pageQuery, items: data.items, loading: false, error: '',
            hasMore: data.has_more, nextOffset: data.next_offset, lastUpdated: new Date() })
        }
      } catch (cause) {
        if (active) {
          const detail = controller.signal.aborted
            ? 'Log isteği zaman aşımına uğradı. Yeniden dene.'
            : cause instanceof Error ? cause.message : 'Loglar yüklenemedi. Yeniden dene.'
          setResult((previous) => ({ ...previous, query: pageQuery, loading: false, error: detail }))
        }
      } finally {
        clearTimeout(timeout)
      }
    }

    loadLogs()
    return () => {
      active = false
      clearTimeout(timeout)
      controller.abort()
    }
  }, [pageQuery, refreshKey, view.offset])

  function changeFilter(name, value) {
    setDraftFilters((previous) => ({ ...previous, [name]: value }))
    setFilterDirty(true)
    setFormError('')
  }

  function applyFilters(event) {
    event.preventDefault()
    try {
      const filters = buildLogFilters(draftFilters)
      setView({ filters, offset: 0 })
      setRefreshKey((value) => value + 1)
      setFilterDirty(false)
      setFormError('')
    } catch (cause) {
      setFormError(cause.message)
    }
  }

  function clearFilters() {
    setDraftFilters({ ...EMPTY_FILTERS })
    setView({ filters: '', offset: 0 })
    setRefreshKey((value) => value + 1)
    setFilterDirty(false)
    setFormError('')
  }

  function openDetails(log, button) {
    detailOpenerRef.current = button
    setSelectedLog(log)
  }

  function closeDetails() {
    setSelectedLog(null)
    // Canlı akış açan satırı listeden çıkarmış olabilir.
    const target = detailOpenerRef.current?.isConnected ? detailOpenerRef.current : headingRef.current
    target?.focus()
  }

  const canGoNext = !loading && !error && hasMore && nextOffset <= MAX_OFFSET
  const shownStreamStatus = view.offset > 0 ? 'paused' : streamStatus

  const streamLabels = {
    connecting: 'Canlı bağlantı kuruluyor…',
    live: 'Canlı akış açık',
    reconnecting: 'Bağlantı kesildi · yeniden bağlanıyor…',
    unavailable: 'Canlı akış veritabanını bekliyor…',
    closed: 'Canlı akış kapandı · yeniden bağlanmak için sayfayı yenile',
    unsupported: 'Tarayıcı canlı akışı desteklemiyor · Logları yenile düğmesini kullan',
    paused: 'Geçmiş sayfa · canlı yenileme duraklatıldı. İlk sayfaya dönünce devam eder.',
  }

  return (
    <>
    <section className="logs-panel" aria-labelledby="logs-title" aria-busy={loading}>
      <div className="logs-heading">
        <div>
          <p className="eyebrow">OLAY KAYITLARI</p>
          <h2 id="logs-title" ref={headingRef} tabIndex={-1}>Log kayıtları</h2>
          <p className="logs-description">Olay zamanına göre yeniden eskiye. Her sayfada en fazla {PAGE_SIZE} kayıt gösterilir.</p>
        </div>
        <button className="secondary-button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}>
          {loading ? 'Yükleniyor…' : 'Logları yenile'}
        </button>
      </div>

      <LogFilters filters={draftFilters} onChange={changeFilter} onApply={applyFilters}
        onClear={clearFilters} error={formError} dirty={filterDirty} />
      <p className={`live-status live-${shownStreamStatus}`} role="status">{streamLabels[shownStreamStatus]}</p>
      {loading && logs.length === 0 && <p className="logs-feedback" role="status">Loglar yükleniyor…</p>}
      {!loading && error && <p className="logs-feedback connection-error" role="alert">{error}</p>}
      {!loading && !error && logs.length === 0 && (
        <p className="logs-feedback" role="status">
          {view.offset > 0 ? 'Bu sayfada kayıt yok. Önceki veya ilk sayfaya dönebilirsin.'
            : view.filters ? 'Bu filtrelerle eşleşen kayıt bulunamadı. Filtreleri değiştirip uygulayabilir veya temizleyebilirsin.'
            : 'Henüz log kaydı yok. Canlı akış açıkken yeni kayıtlar otomatik görünür.'}
        </p>
      )}
      {!error && logs.length > 0 && (
        <>
          <div className="logs-scroll" role="region" aria-label="Log tablosu" tabIndex={0}>
            <table className="logs-table">
              <caption className="sr-only">Zaman, servis, seviye ve mesaj bilgileriyle filtrelenmiş log kayıtları</caption>
              <thead>
                <tr><th scope="col">Zaman</th><th scope="col">Servis</th><th scope="col">Seviye</th><th scope="col">Mesaj</th><th scope="col">İşlem</th></tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={`${log.timestamp}-${log.id}`}>
                    <td className="log-time"><time dateTime={log.timestamp}>{formatTime(log.timestamp)}</time></td>
                    <td className="log-service">{log.service}</td>
                    <td><span className={`log-level level-${log.level}`}>{log.level}</span></td>
                    <td className="log-message"><span className="log-message-preview">{log.message}</span></td>
                    <td><button type="button" className="secondary-button log-detail-button"
                      aria-label={`${log.service} servisinin ${log.id} numaralı logunun detayını aç`}
                      onClick={(event) => openDetails(log, event.currentTarget)}>Detay</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="logs-footer">
        <p role="status">
          Sayfa {view.offset / PAGE_SIZE + 1} · {loading ? 'Yükleniyor…' : error ? 'Yüklenemedi'
            : logs.length ? `${view.offset + 1}–${view.offset + logs.length}. kayıtlar` : 'Kayıt yok'}
          {lastUpdated && !error && <> · Son güncelleme: <time dateTime={lastUpdated.toISOString()}>{lastUpdated.toLocaleTimeString('tr-TR')}</time></>}
        </p>
        <nav className="pagination" aria-label="Log sayfaları">
          {view.offset > 0 && <button type="button" className="secondary-button" disabled={loading}
            onClick={() => setView((previous) => ({ ...previous, offset: 0 }))}>İlk sayfa / canlı</button>}
          <button type="button" className="secondary-button" disabled={loading || view.offset === 0}
            onClick={() => setView((previous) => ({ ...previous, offset: Math.max(0, previous.offset - PAGE_SIZE) }))}>Önceki</button>
          <button type="button" className="secondary-button" disabled={!canGoNext}
            onClick={() => setView((previous) => ({ ...previous, offset: nextOffset }))}>Sonraki</button>
        </nav>
        {!loading && !error && hasMore && nextOffset > MAX_OFFSET && (
          <p className="pagination-note">Görüntüleme sınırına ulaşıldı. Zaman aralığını daraltarak devam edebilirsin.</p>
        )}
        {view.offset > 0 && <p className="pagination-note">Yeni kayıtlar geldiğinde sayfa sırası değişebilir.</p>}
      </div>
    </section>
    <LogDetails log={selectedLog} onClose={closeDetails} />
    </>
  )
}
