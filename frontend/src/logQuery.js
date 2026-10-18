export const PAGE_SIZE = 20
export const MAX_OFFSET = 100000
export const EMPTY_FILTERS = { service: '', level: '', q: '', start: '', end: '' }

export function buildLogFilters(filters) {
  const params = new URLSearchParams()
  for (const key of ['service', 'level', 'q']) {
    const value = filters[key].trim()
    if (value) params.set(key, value)
  }
  const dates = {}
  for (const key of ['start', 'end']) {
    if (!filters[key]) continue
    const date = new Date(filters[key])
    if (Number.isNaN(date.getTime())) throw new Error('Geçerli bir başlangıç ve bitiş zamanı seç.')
    dates[key] = date
    params.set(key, date.toISOString())
  }
  if (dates.start && dates.end && dates.start > dates.end) {
    throw new Error('Başlangıç zamanı bitiş zamanından sonra olamaz.')
  }
  return params.toString()
}

export function buildLogPageQuery(filters, offset) {
  if (!Number.isInteger(offset) || offset < 0 || offset > MAX_OFFSET || offset % PAGE_SIZE !== 0) {
    throw new Error('Geçersiz sayfa numarası.')
  }
  const params = new URLSearchParams(filters)
  params.set('limit', PAGE_SIZE)
  params.set('offset', offset)
  return params.toString()
}
