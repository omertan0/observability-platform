export const ALERT_PAGE_SIZE = 20
export const ALERT_MAX_OFFSET = 100000
export const EMPTY_ALERT_FILTERS = { service: '', status: 'open' }
const validTime = (value) => typeof value === 'string' && Number.isFinite(Date.parse(value))

export function buildAlertFilters({ service, status }) {
  const params = new URLSearchParams()
  const selectedService = service.trim()
  if (selectedService.length > 200) throw new Error('Servis adı en fazla 200 karakter olabilir.')
  if (!['', 'open', 'acknowledged'].includes(status)) throw new Error('Geçerli bir alarm durumu seç.')
  if (selectedService) params.set('service', selectedService)
  if (status) params.set('status', status)
  return params.toString()
}

export function buildAlertPageQuery(filters, offset) {
  if (!Number.isInteger(offset) || offset < 0 || offset > ALERT_MAX_OFFSET || offset % ALERT_PAGE_SIZE !== 0) {
    throw new Error('Geçersiz alarm sayfası.')
  }
  const params = new URLSearchParams(filters)
  params.set('limit', String(ALERT_PAGE_SIZE))
  params.set('offset', String(offset))
  return params.toString()
}

export function validateAlertPage(data, offset) {
  if (!data || !Array.isArray(data.items) || data.items.length > ALERT_PAGE_SIZE || data.limit !== ALERT_PAGE_SIZE
    || data.offset !== offset || typeof data.has_more !== 'boolean'
    || data.next_offset !== (data.has_more ? offset + ALERT_PAGE_SIZE : null)) {
    throw new Error('API beklenen alarm listesini döndürmedi.')
  }
  for (const alert of data.items) {
    if (!alert || !Number.isSafeInteger(alert.id) || alert.id < 1 || typeof alert.rule_name !== 'string'
      || typeof alert.service !== 'string' || typeof alert.message !== 'string'
      || !['metric_threshold', 'log_count'].includes(alert.kind)
      || !['open', 'acknowledged'].includes(alert.status) || !validTime(alert.triggered_at)
      || (alert.acknowledged_at !== null && !validTime(alert.acknowledged_at))
      || (alert.status === 'acknowledged' && !validTime(alert.acknowledged_at))) {
      throw new Error('API geçerli alarm kayıtları döndürmedi.')
    }
  }
  return data
}

export function validateAcknowledgment(data, id) {
  if (!data || data.id !== id || data.status !== 'acknowledged' || !validTime(data.acknowledged_at)) {
    throw new Error('İşlem yanıtı doğrulanamadı. Alarm listesini yenileyerek durumunu kontrol et.')
  }
  return data
}
