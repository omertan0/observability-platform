import { useEffect, useState } from 'react'
import { apiFetch, notifySessionExpired } from './apiClient.js'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { buildMetricQuery, METRIC_LIMIT, METRIC_WINDOWS, METRIC_TYPES, metricType, formatMetricValue, metricPoints, metricWindow, metricTicks, metricTickLabel, timeDomain } from './metricQuery.js'

const EMPTY_RESULT = { query: null, points: [], loading: true, error: '', hasMore: false, updatedAt: null }
const dateFormatter = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'short', timeStyle: 'medium' })
const streamLabels = {
  connecting: 'Metrik bağlantısı kuruluyor…',
  live: 'Metrik akışı açık · yeni kayıtlar otomatik yüklenir',
  reconnecting: 'Metrik bağlantısı kesildi · yeniden bağlanıyor…',
  unavailable: 'Metrik akışı veritabanını bekliyor…',
  closed: 'Metrik akışı kapandı · bağlantı için sayfayı yenile',
  unsupported: 'Tarayıcı canlı akışı desteklemiyor · Metrikleri yenile düğmesini kullan',
}

function MetricTimeTick({ x, y, payload, span }) {
  const label = metricTickLabel(payload.value, span)
  return <text x={x} y={y + 12} textAnchor="middle" fill="#aab6c7" fontSize={11}>
    <tspan x={x}>{label.time}</tspan>
    <tspan x={x} dy={16}>{label.date}</tspan>
  </text>
}

function MetricTooltip({ active, payload, points, metricKey }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  const sameTime = points.filter((item) => item.time === point.time)
  return <div className="metric-tooltip">
    <time dateTime={point.timestamp}>{dateFormatter.format(point.time)}</time>
    {sameTime.map((item) => <strong key={item.id}>{metricType(metricKey).shortLabel}: {formatMetricValue(item.value, metricKey)}</strong>)}
    {sameTime.length > 1 && <span>Aynı ölçüm zamanında {sameTime.length} ayrı kayıt</span>}
    <span>{point.service}</span>
  </div>
}

export default function MetricsPanel() {
  const [draftService, setDraftService] = useState('payment-service')
  const [service, setService] = useState('payment-service')
  const [draftMetricKey, setDraftMetricKey] = useState('cpu')
  const [metricKey, setMetricKey] = useState('cpu')
  const [formError, setFormError] = useState('')
  const [result, setResult] = useState(EMPTY_RESULT)
  const [refreshKey, setRefreshKey] = useState(0)
  const [streamStatus, setStreamStatus] = useState('connecting')
  const [windowKey, setWindowKey] = useState('1h')
  const [chartWidth, setChartWidth] = useState(320)
  const type = metricType(metricKey)
  const query = buildMetricQuery(service, metricKey)
  const { points, loading, error, hasMore, updatedAt } = result.query === query ? result : EMPTY_RESULT
  const latest = points.at(-1)
  const shownPoints = metricWindow(points, windowKey)
  const domain = timeDomain(shownPoints)
  const duplicateCount = shownPoints.length - new Set(shownPoints.map((point) => point.time)).size

  useEffect(() => {
    if (!('EventSource' in window)) {
      setStreamStatus('unsupported')
      return
    }
    let active = true
    setStreamStatus('connecting')
    const stream = new EventSource(`/api/stream/metrics?${query}`)
    stream.onopen = () => { if (active) setStreamStatus('connecting') }
    stream.addEventListener('metrics_changed', () => {
      if (!active) return
      setStreamStatus('live')
      setRefreshKey((value) => value + 1)
    })
    stream.addEventListener('stream_status', () => { if (active) setStreamStatus('unavailable') })
    stream.addEventListener('auth_expired', () => { if (active) { stream.close(); notifySessionExpired() } })
    stream.onerror = () => {
      if (active) setStreamStatus(stream.readyState === EventSource.CLOSED ? 'closed' : 'reconnecting')
    }
    return () => { active = false; stream.close() }
  }, [query])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = setTimeout(() => controller.abort(), 15000)
    async function loadMetrics() {
      setResult((previous) => ({ ...(previous.query === query ? previous : EMPTY_RESULT), query, loading: true, error: '' }))
      try {
        const response = await apiFetch(`/api/metrics?${query}`, { signal: controller.signal })
        if (!response.ok) throw new Error(`Metrikler alınamadı (HTTP ${response.status}). Servisleri kontrol edip yeniden dene.`)
        const data = await response.json()
        const receivedPoints = metricPoints(data, service, metricKey)
        if (active) setResult({ query, points: receivedPoints, loading: false, error: '', hasMore: data.has_more, updatedAt: new Date() })
      } catch (cause) {
        if (active) setResult((previous) => ({ ...previous, query, loading: false,
          error: controller.signal.aborted ? 'Metrik isteği zaman aşımına uğradı. Yeniden dene.'
            : cause instanceof Error ? cause.message : 'Metrikler yüklenemedi. Yeniden dene.' }))
      } finally {
        clearTimeout(timeout)
      }
    }
    loadMetrics()
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [query, refreshKey, service, metricKey])

  function applyService(event) {
    event.preventDefault()
    try {
      buildMetricQuery(draftService, draftMetricKey)
      setService(draftService.trim())
      setMetricKey(draftMetricKey)
      setRefreshKey((value) => value + 1)
      setFormError('')
    } catch (cause) { setFormError(cause.message) }
  }

  return (
    <section className="logs-panel metrics-panel" aria-labelledby="metrics-title">
      <div className="logs-heading">
        <div>
          <p className="eyebrow">PERFORMANS ÖLÇÜMLERİ</p>
          <h2 id="metrics-title">{type.label}</h2>
          <p className="logs-description">Seçilen servis ve metrik için olay zamanına göre son {METRIC_LIMIT} ölçüm. Yeni ölçümler geldikçe grafik güncellenir.</p>
        </div>
        <button className="secondary-button" disabled={loading} onClick={() => setRefreshKey((value) => value + 1)}>
          {loading ? 'Yükleniyor…' : 'Metrikleri yenile'}
        </button>
      </div>
      <form className="metric-filter" onSubmit={applyService}>
        <label htmlFor="metric-service">Servis adı (tam eşleşme)
          <input id="metric-service" maxLength={200} required value={draftService}
            onChange={(event) => { setDraftService(event.target.value); setFormError('') }} />
        </label>
        <label htmlFor="metric-type">Metrik
          <select id="metric-type" value={draftMetricKey} onChange={(event) => { setDraftMetricKey(event.target.value); setFormError('') }}>
            {METRIC_TYPES.map((item) => <option key={item.key} value={item.key}>{item.label} ({item.percent ? '%' : item.unit})</option>)}
          </select>
        </label>
        <button type="submit" className="secondary-button">Göster</button>
        {(draftService.trim() !== service || draftMetricKey !== metricKey) && <p className="filter-notice">Servis veya metrik değişikliğini uygulamak için Göster’e bas.</p>}
        {formError && <p className="filter-error" role="alert">{formError}</p>}
      </form>
      <p className={`live-status live-${streamStatus}`} role="status">{streamLabels[streamStatus]}</p>
      <div aria-busy={loading}>
        {error && <p className="logs-feedback connection-error" role="alert">{error}{points.length > 0 && ' Önceki ölçümler gösteriliyor; güncellikleri doğrulanamadı.'}</p>}
        {loading && points.length === 0 && <p className="logs-feedback">Metrik ölçümleri yükleniyor…</p>}
        {!loading && !error && points.length === 0 && <p className="logs-feedback">{service} için kayıtlı {type.label.toLocaleLowerCase('tr-TR')} bulunamadı. API’ye {type.name} / {type.unit} ölçümü gönderildiğinde burada görünür.</p>}
        {latest && <>
          <div className="metric-summary">
            <div><span>Kayıtlı son ölçüm · {service}</span><strong>{formatMetricValue(latest.value, metricKey)}</strong></div>
            <div><span>Ölçüm zamanı</span><time dateTime={latest.timestamp}>{dateFormatter.format(latest.time)}</time>
              <small>Bu değer cihazdan şimdi okunmaz; gönderilen kaydın zamanını kontrol et.</small></div>
          </div>
          <div className="metric-window">
            <div role="group" aria-label="Son ölçüme göre grafik zaman aralığı">
              {METRIC_WINDOWS.map((window) => <button key={window.key} type="button" className="secondary-button"
                aria-pressed={windowKey === window.key} onClick={() => setWindowKey(window.key)}>{window.label}</button>)}
            </div>
            <p>Aralık, kayıtlı son ölçümden geriye doğru uygulanır. {shownPoints.length} / {points.length} kayıt gösteriliyor.</p>
            <p>Gösterilen ölçümler: {dateFormatter.format(shownPoints[0].time)} → {dateFormatter.format(shownPoints.at(-1).time)}</p>
          </div>
          <div className="metric-chart" role="group" aria-label={`${service} ${type.label.toLocaleLowerCase('tr-TR')} grafiği. Birim: ${type.unit}. Sayısal veriler altındaki tabloda.`}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} onResize={(width) => setChartWidth(width)}>
              <LineChart data={shownPoints} margin={{ top: 15, right: 50, bottom: 15, left: 0 }} accessibilityLayer>
                <CartesianGrid stroke="#303a49" strokeDasharray="3 5" />
                <XAxis dataKey="time" type="number" scale="time" domain={domain} ticks={metricTicks(shownPoints, chartWidth)}
                  height={52} interval="preserveStartEnd" minTickGap={24} tickMargin={8}
                  tickFormatter={(value) => metricTickLabel(value, domain[1] - domain[0]).time}
                  tick={<MetricTimeTick span={domain[1] - domain[0]} />} />
                <YAxis domain={type.percent ? [0, 100] : [0, 'auto']} ticks={type.percent ? [0, 25, 50, 75, 100] : undefined}
                  unit={type.percent ? '%' : ' ms'} width={76} tick={{ fill: '#aab6c7', fontSize: 11 }} />
                <Tooltip content={<MetricTooltip points={shownPoints} metricKey={metricKey} />} />
                <Line type="linear" dataKey="value" name={type.shortLabel} stroke="#98bcff" strokeWidth={2}
                  dot={{ r: 3, fill: '#98bcff', strokeWidth: 0 }} activeDot={{ r: 5 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="metric-note">Yatay eksen ölçüm zamanı, dikey eksen {type.percent ? 'kullanım yüzdesidir' : 'milisaniye cinsinden yanıt süresidir'}. Noktaları birleştiren çizgi aradaki sürelerde yeni ölçüm yapıldığı anlamına gelmez.
            {shownPoints.length === 1 && ' Bu aralıkta tek ölçüm var; çizgi için ikinci bir ölçüm gerekir.'}
            {duplicateCount > 0 && ' Aynı ölçüm zamanına sahip kayıtlar var; aynı dikey hizada görünmeleri normaldir. Noktanın bilgi kutusunda tüm değerler listelenir.'}</p>
          <details className="metric-data">
            <summary>Bu aralıktaki ölçümleri tablo olarak göster ({shownPoints.length})</summary>
            <div className="logs-scroll" tabIndex={0} role="region" aria-label={`${type.label} ölçüm tablosu`}>
              <table className="logs-table metric-table"><caption className="sr-only">{service} {type.label.toLocaleLowerCase('tr-TR')} ölçümleri, eskiden yeniye</caption>
                <thead><tr><th scope="col">ÖLÇÜM ZAMANI</th><th scope="col">{type.shortLabel.toLocaleUpperCase('tr-TR')} ({type.percent ? '%' : type.unit})</th></tr></thead>
                <tbody>{shownPoints.map((point) => <tr key={point.id}><td><time dateTime={point.timestamp}>{dateFormatter.format(point.time)}</time></td><td>{formatMetricValue(point.value, metricKey)}</td></tr>)}</tbody>
              </table>
            </div>
          </details>
        </>}
      </div>
      <p className="logs-footer">Gösterilen servis: {service}. {hasMore ? `Daha eski ölçümler var; son ${METRIC_LIMIT} kayıt yüklendi.` : `${points.length} kayıt yüklendi.`}
        {updatedAt && ` Son başarılı veri alımı: ${dateFormatter.format(updatedAt)}.`}</p>
    </section>
  )
}
