import { useEffect, useRef, useState } from 'react'
import { apiFetch } from './apiClient.js'
import { ALERT_PAGE_SIZE, ALERT_MAX_OFFSET, EMPTY_ALERT_FILTERS, buildAlertFilters, buildAlertPageQuery, validateAlertPage, validateAcknowledgment } from './alertQuery.js'

const EMPTY_RESULT = { query: null, items: [], loading: true, error: '', hasMore: false, nextOffset: null, updatedAt: null }
const dateFormatter = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'short', timeStyle: 'medium' })
const formatTime = (value) => dateFormatter.format(new Date(value))

export default function AlertsPanel() {
  const [draftFilters, setDraftFilters] = useState({ ...EMPTY_ALERT_FILTERS })
  const [view, setView] = useState({ filters: buildAlertFilters(EMPTY_ALERT_FILTERS), offset: 0 })
  const [result, setResult] = useState(EMPTY_RESULT)
  const [refreshKey, setRefreshKey] = useState(0)
  const [formError, setFormError] = useState('')
  const [notice, setNotice] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const acknowledgmentRef = useRef(null)
  const noticeRef = useRef(null)
  const query = buildAlertPageQuery(view.filters, view.offset)
  const { items: alerts, loading, error, hasMore, nextOffset, updatedAt } = result.query === query ? result : EMPTY_RESULT
  const appliedFilters = new URLSearchParams(view.filters)
  const dirty = draftFilters.service.trim() !== (appliedFilters.get('service') || '')
    || draftFilters.status !== (appliedFilters.get('status') || '')

  useEffect(() => { if (notice) noticeRef.current?.focus() }, [notice])

  useEffect(() => () => {
    const controller = acknowledgmentRef.current
    acknowledgmentRef.current = null
    controller?.abort()
  }, [])

  useEffect(() => {
    // Bir alarm değiştirilirken eski bir GET yanıtı durumu geri çevirmesin.
    if (busyId !== null) return
    let active = true
    let controller
    let pollTimer
    let requestTimer
    async function loadAlerts() {
      controller = new AbortController()
      requestTimer = setTimeout(() => controller.abort(), 15000)
      setResult((previous) => ({ ...(previous.query === query ? previous : EMPTY_RESULT), query, loading: true, error: '' }))
      try {
        const response = await apiFetch(`/api/alerts?${query}`, { signal: controller.signal })
        if (!response.ok) throw new Error(response.status === 503
          ? 'Veritabanına erişilemiyor. Servisleri kontrol edip yeniden dene.'
          : `Alarmlar alınamadı (HTTP ${response.status}). Yeniden dene.`)
        const data = validateAlertPage(await response.json(), view.offset)
        if (active) setResult({ query, items: data.items, loading: false, error: '',
          hasMore: data.has_more, nextOffset: data.next_offset, updatedAt: new Date() })
      } catch (cause) {
        if (active) setResult((previous) => ({ ...previous, query, loading: false,
          error: controller.signal.aborted ? 'Alarm isteği zaman aşımına uğradı. Yeniden dene.'
            : cause instanceof Error ? cause.message : 'Alarmlar yüklenemedi.' }))
      } finally {
        clearTimeout(requestTimer)
        // Önceki istek tamamlandıktan sonra bekle; istekler üst üste binmez.
        if (active && view.offset === 0) pollTimer = setTimeout(loadAlerts, 10000)
      }
    }
    loadAlerts()
    return () => { active = false; clearTimeout(pollTimer); clearTimeout(requestTimer); controller?.abort() }
  }, [query, refreshKey, view.offset, busyId])

  function changeFilter(key, value) {
    setDraftFilters((previous) => ({ ...previous, [key]: value }))
    setFormError('')
  }

  function applyFilters(event) {
    event.preventDefault()
    try {
      setView({ filters: buildAlertFilters(draftFilters), offset: 0 })
      setRefreshKey((value) => value + 1)
      setFormError('')
      setNotice(null)
    } catch (cause) { setFormError(cause.message) }
  }

  async function acknowledge(alert) {
    if (acknowledgmentRef.current) return
    const controller = new AbortController()
    acknowledgmentRef.current = controller
    setBusyId(alert.id)
    setNotice(null)
    const timeout = setTimeout(() => controller.abort(), 15000)
    try {
      const response = await apiFetch(`/api/alerts/${alert.id}/acknowledge`, { method: 'PATCH', signal: controller.signal })
      if (!response.ok) throw new Error(response.status === 404
        ? 'Bu alarm artık bulunamıyor. Listeyi yenile.'
        : `İşlem doğrulanamadı (HTTP ${response.status}). Listeyi yenileyerek alarmın durumunu kontrol et.`)
      validateAcknowledgment(await response.json(), alert.id)
      if (acknowledgmentRef.current === controller) setNotice({ kind: 'success', message: `${alert.id} numaralı alarm görüldü olarak kaydedildi. Bu işlem sorunun çözüldüğünü belirtmez.` })
    } catch (cause) {
      if (acknowledgmentRef.current === controller) setNotice({ kind: 'error', message: controller.signal.aborted
        ? 'İstek zaman aşımına uğradı. İşlem kaydedilmiş olabilir; alarmın durumunu listeden kontrol et.'
        : `${cause instanceof Error ? cause.message : 'İşlem tamamlanamadı.'} Durum belirsizse listeyi yenile.` })
    } finally {
      clearTimeout(timeout)
      if (acknowledgmentRef.current === controller) {
        acknowledgmentRef.current = null
        setBusyId(null)
        // PATCH sonrası filtre ve has_more bilgileri yeniden sunucudan alınır.
        setRefreshKey((value) => value + 1)
      }
    }
  }

  return (
    <section className="logs-panel alerts-panel" aria-labelledby="alerts-title">
      <div className="logs-heading">
        <div>
          <p className="eyebrow">ALARM BİLDİRİMLERİ</p>
          <h2 id="alerts-title">Alarmlar</h2>
          <p className="logs-description">Kuralların ürettiği bildirimler, yeniden eskiye. Görüldü işareti alarmın incelendiğini kaydeder; sorunun çözüldüğü anlamına gelmez.</p>
        </div>
        <button className="secondary-button" disabled={loading || busyId !== null} onClick={() => setRefreshKey((value) => value + 1)}>
          {loading ? 'Yükleniyor…' : 'Alarmları yenile'}
        </button>
      </div>
      <form className="alert-filters" onSubmit={applyFilters}>
        <fieldset className="metric-filter" disabled={busyId !== null}>
          <legend className="sr-only">Alarm filtreleri</legend>
          <label htmlFor="alert-service">Servis adı (tam eşleşme)
            <input id="alert-service" maxLength={200} placeholder="Tüm servisler" value={draftFilters.service}
              onChange={(event) => changeFilter('service', event.target.value)} />
          </label>
          <label htmlFor="alert-status">Durum
            <select id="alert-status" value={draftFilters.status} onChange={(event) => changeFilter('status', event.target.value)}>
              <option value="open">İncelenmeyenler</option><option value="acknowledged">Görüldü</option><option value="">Tümü</option>
            </select>
          </label>
          <button className="secondary-button" type="submit">Uygula</button>
          {dirty && <p className="filter-notice">Filtre değişikliğini uygulamak için Uygula’ya bas.</p>}
          {formError && <p className="filter-error" role="alert">{formError}</p>}
        </fieldset>
      </form>
      <p className="live-status">{view.offset === 0 ? 'İlk sayfa yaklaşık 10 saniyede bir yenilenir.' : 'Geçmiş sayfa · otomatik yenileme duraklatıldı.'}</p>
      {notice && <p ref={noticeRef} tabIndex={-1} className={`alert-notice ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>{notice.message}</p>}
      <div aria-busy={loading}>
        {error && <p className="logs-feedback connection-error" role="alert">{error}{alerts.length > 0 && ' Önceki liste gösteriliyor; güncelliği doğrulanamadı.'}</p>}
        {loading && alerts.length === 0 && <p className="logs-feedback" role="status">Alarmlar yükleniyor…</p>}
        {!loading && !error && alerts.length === 0 && <p className="logs-feedback" role="status">{view.offset > 0
          ? 'Bu sayfada kayıt kalmadı. Önceki veya ilk sayfaya dönebilirsin.'
          : 'Seçili filtrelerle eşleşen alarm bulunamadı. Bu sonuç sistemde sorun olmadığını tek başına göstermez.'}</p>}
        {alerts.length > 0 && <div className="logs-scroll" tabIndex={0} role="region" aria-label="Alarm tablosu">
          <table className="logs-table alerts-table">
            <caption className="sr-only">Alarm zamanı, servis, kural, mesaj ve inceleme durumu</caption>
            <thead><tr><th scope="col">ALARM ZAMANI</th><th scope="col">SERVİS</th><th scope="col">KURAL VE AÇIKLAMA</th><th scope="col">DURUM</th><th scope="col">İŞLEM</th></tr></thead>
            <tbody>{alerts.map((alert) => <tr key={alert.id}>
              <td className="log-time"><time dateTime={alert.triggered_at}>{formatTime(alert.triggered_at)}</time><small>#{alert.id}</small></td>
              <td className="log-service">{alert.service}</td>
              <td className="alert-description"><strong>{alert.rule_name}</strong><span className="alert-kind">{alert.kind === 'metric_threshold' ? 'Metrik eşiği' : 'Log sayısı'}</span><p>{alert.message}</p></td>
              <td><span className={`status ${alert.status === 'open' ? 'unavailable' : 'ready'}`}>{alert.status === 'open' ? 'İncelenmedi' : 'Görüldü'}</span>
                {alert.acknowledged_at && <time className="alert-ack-time" dateTime={alert.acknowledged_at}>{formatTime(alert.acknowledged_at)}</time>}</td>
              <td>{alert.status === 'open' ? <button type="button" className="secondary-button log-detail-button" disabled={busyId !== null}
                aria-label={`${alert.id} numaralı ${alert.service} alarmını görüldü olarak işaretle`} onClick={() => acknowledge(alert)}>
                {busyId === alert.id ? 'Kaydediliyor…' : 'Görüldü işaretle'}</button> : <span className="alert-completed">İşaretlendi</span>}</td>
            </tr>)}</tbody>
          </table>
        </div>}
      </div>
      <div className="logs-footer">
        <p role="status">Sayfa {view.offset / ALERT_PAGE_SIZE + 1} · {loading ? 'Yükleniyor…' : error ? 'Güncel liste alınamadı' : `${alerts.length} kayıt`}{updatedAt && ` · Son başarılı veri alımı: ${formatTime(updatedAt)}`}</p>
        <nav className="pagination" aria-label="Alarm sayfaları">
          {view.offset > 0 && <button className="secondary-button" disabled={loading || busyId !== null} onClick={() => setView((previous) => ({ ...previous, offset: 0 }))}>İlk sayfa</button>}
          <button className="secondary-button" disabled={loading || busyId !== null || view.offset === 0}
            onClick={() => setView((previous) => ({ ...previous, offset: previous.offset - ALERT_PAGE_SIZE }))}>Önceki</button>
          <button className="secondary-button" disabled={loading || busyId !== null || !!error || !hasMore || nextOffset > ALERT_MAX_OFFSET}
            onClick={() => setView((previous) => ({ ...previous, offset: nextOffset }))}>Sonraki</button>
        </nav>
        {hasMore && nextOffset > ALERT_MAX_OFFSET && <p className="pagination-note">Görüntüleme sınırına ulaşıldı. Servis veya durum filtresiyle sonuçları daralt.</p>}
        {view.offset > 0 && <p className="pagination-note">Yeni alarmlar ve görüldü işaretleri sayfa sırasını değiştirebilir.</p>}
      </div>
    </section>
  )
}
