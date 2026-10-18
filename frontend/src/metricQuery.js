export const METRIC_LIMIT = 100
export const CPU_NAME = 'cpu_usage'
export const CPU_UNIT = 'percent'
export const METRIC_TYPES = [
  { key: 'cpu', label: 'CPU kullanımı', shortLabel: 'CPU', name: CPU_NAME, unit: CPU_UNIT, percent: true },
  { key: 'memory', label: 'Bellek kullanımı', shortLabel: 'Bellek', name: 'memory_usage', unit: 'percent', percent: true },
  { key: 'response', label: 'Yanıt süresi', shortLabel: 'Yanıt süresi', name: 'response_time', unit: 'ms', percent: false },
]

export function metricType(key) {
  const type = METRIC_TYPES.find((item) => item.key === key)
  if (!type) throw new Error('Geçersiz metrik seçimi.')
  return type
}

const metricNumberFormatter = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 3 })

export function formatMetricValue(value, key) {
  const type = metricType(key)
  const number = metricNumberFormatter.format(value)
  return type.percent ? `%${number}` : `${number} ${type.unit}`
}
export const METRIC_WINDOWS = [
  { key: '1h', label: '1 saat', duration: 3600000 },
  { key: '24h', label: '24 saat', duration: 86400000 },
  { key: 'all', label: 'Tüm kayıtlar', duration: Infinity },
]

export function buildMetricQuery(service, metricKey = 'cpu') {
  const type = metricType(metricKey)
  const selected = service.trim()
  if (!selected || selected.length > 200) throw new Error('1–200 karakterlik bir servis adı yaz.')
  return new URLSearchParams({ service: selected, name: type.name, unit: type.unit, limit: String(METRIC_LIMIT) }).toString()
}

export function metricPoints(data, service, metricKey = 'cpu') {
  const type = metricType(metricKey)
  if (!Array.isArray(data.items) || data.items.length > METRIC_LIMIT
    || data.limit !== METRIC_LIMIT || data.offset !== 0 || typeof data.has_more !== 'boolean') {
    throw new Error('API beklenen metrik listesini döndürmedi.')
  }
  const points = data.items.map((metric) => {
    const time = Date.parse(metric.timestamp)
    if (metric.service !== service || metric.name !== type.name || metric.unit !== type.unit
      || !Number.isFinite(time) || typeof metric.value !== 'number'
      || !Number.isFinite(metric.value) || metric.value < 0 || (type.percent && metric.value > 100)) {
      throw new Error(`API geçerli ${type.label.toLocaleLowerCase('tr-TR')} ölçümleri döndürmedi.`)
    }
    return { ...metric, time }
  })
  // API yeniden eskiye döner; grafik soldan sağa eski → yeni okunur.
  return points.reverse().sort((left, right) => left.time - right.time)
}

export function timeDomain(points) {
  if (!points.length) return [0, 1]
  const start = points[0].time
  const end = points.at(-1).time
  // Tek zaman noktasında da görünür bir eksen ve nokta olsun.
  return start === end ? [start - 30000, end + 30000] : [start, end]
}

export function metricWindow(points, windowKey) {
  const selected = METRIC_WINDOWS.find((window) => window.key === windowKey)
  if (!selected) throw new Error('Geçersiz grafik zaman aralığı.')
  if (!points.length) return []
  const cutoff = points.at(-1).time - selected.duration
  return points.filter((point) => point.time >= cutoff)
}

export function metricTicks(points, width) {
  const [start, end] = timeDomain(points)
  // Her etiket için yer ayır; dar ekranda yalnızca başlangıç ve bitişi yaz.
  const count = Math.max(2, Math.min(6, Math.floor((width - 100) / 100)))
  return Array.from({ length: count }, (_, index) => start + (end - start) * index / (count - 1))
}

export function metricTickLabel(time, span) {
  const options = { hour: '2-digit', minute: '2-digit' }
  if (span <= 300000) options.second = '2-digit'
  if (span < 10000) options.fractionalSecondDigits = 3
  return {
    date: new Intl.DateTimeFormat('tr-TR', { day: '2-digit', month: '2-digit' }).format(time),
    time: new Intl.DateTimeFormat('tr-TR', options).format(time),
  }
}
