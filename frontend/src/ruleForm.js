export const RULE_PAGE_SIZE = 20
export const RULE_MAX_OFFSET = 100000
export const RULE_LEVELS = ['INFO', 'WARN', 'ERROR', 'FATAL']
export const RULE_OPERATORS = { gt: '>', gte: '≥', lt: '<', lte: '≤' }
export const EMPTY_RULE = {
  name: '', kind: 'metric_threshold', service: 'payment-service',
  metric_name: 'cpu_usage', metric_unit: 'percent', level: 'ERROR',
  operator: 'gt', threshold: '85', window_seconds: '300', cooldown_seconds: '300', enabled: true,
}

function text(value, label, max) {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > max) throw new Error(`${label}: 1–${max} karakter yaz.`)
  return value.trim()
}

function number(value, label, min = -Infinity, max = Infinity, integer = false) {
  const parsed = typeof value === 'string' && value.trim() ? Number(value) : NaN
  if (!Number.isFinite(parsed) || parsed < min || parsed > max || (integer && !Number.isSafeInteger(parsed))) {
    throw new Error(`${label}: geçerli ${integer ? 'bir tam sayı' : 'bir sayı'} yaz${Number.isFinite(min) && Number.isFinite(max) ? ` (${min}–${max})` : ''}.`)
  }
  return parsed
}

export function buildRulePayload(draft) {
  if (!['metric_threshold', 'log_count'].includes(draft.kind)) throw new Error('Geçerli bir kural türü seç.')
  if (!Object.hasOwn(RULE_OPERATORS, draft.operator) || (draft.kind === 'log_count' && !['gt', 'gte'].includes(draft.operator))) {
    throw new Error('Bu kural türü için geçerli bir karşılaştırma seç.')
  }
  if (typeof draft.enabled !== 'boolean') throw new Error('Kuralın etkinlik durumu geçersiz.')
  const log = draft.kind === 'log_count'
  if (log && !RULE_LEVELS.includes(draft.level)) throw new Error('Geçerli bir log seviyesi seç.')
  const service = draft.service.trim()
  if (service.length > 200) throw new Error('Servis adı en fazla 200 karakter olabilir.')
  return {
    name: text(draft.name, 'Kural adı', 200), kind: draft.kind, service: service || null,
    metric_name: log ? null : text(draft.metric_name, 'Metrik adı', 200),
    metric_unit: log ? null : text(draft.metric_unit, 'Metrik birimi', 50), level: log ? draft.level : null,
    operator: draft.operator,
    threshold: number(draft.threshold, 'Eşik', log ? 0 : -Infinity, Infinity, log),
    window_seconds: log ? number(draft.window_seconds, 'Zaman penceresi (saniye)', 1, 86400, true) : 300,
    cooldown_seconds: number(draft.cooldown_seconds, 'Tekrar bekleme (saniye)', 0, 86400, true),
    enabled: draft.enabled,
  }
}

export function ruleToDraft(rule) {
  return { name: rule.name, kind: rule.kind, service: rule.service ?? '', metric_name: rule.metric_name ?? '',
    metric_unit: rule.metric_unit ?? '', level: rule.level ?? 'ERROR', operator: rule.operator,
    threshold: String(rule.threshold), window_seconds: String(rule.window_seconds),
    cooldown_seconds: String(rule.cooldown_seconds), enabled: rule.enabled }
}

export function buildRuleQuery(offset) {
  if (!Number.isInteger(offset) || offset < 0 || offset > RULE_MAX_OFFSET || offset % RULE_PAGE_SIZE !== 0) throw new Error('Geçersiz kural sayfası.')
  return new URLSearchParams({ limit: String(RULE_PAGE_SIZE), offset: String(offset) }).toString()
}

export function validateRule(rule) {
  try {
    if (!rule || !Number.isSafeInteger(rule.id) || rule.id < 1
      || typeof rule.threshold !== 'number' || typeof rule.window_seconds !== 'number' || typeof rule.cooldown_seconds !== 'number'
      || !Number.isInteger(rule.window_seconds) || rule.window_seconds < 1 || rule.window_seconds > 86400
      || typeof rule.updated_at !== 'string' || typeof rule.created_at !== 'string'
      || !Number.isFinite(Date.parse(rule.updated_at)) || !Number.isFinite(Date.parse(rule.created_at))) throw new Error()
    const payload = buildRulePayload(ruleToDraft(rule))
    if (rule.service !== payload.service || rule.metric_name !== payload.metric_name || rule.metric_unit !== payload.metric_unit || rule.level !== payload.level) throw new Error()
  } catch { throw new Error('API geçerli alarm kuralı döndürmedi.') }
  return rule
}

export function validateRulePage(data, offset) {
  if (!data || !Array.isArray(data.items) || data.items.length > RULE_PAGE_SIZE || data.limit !== RULE_PAGE_SIZE
    || data.offset !== offset || typeof data.has_more !== 'boolean'
    || data.next_offset !== (data.has_more ? offset + RULE_PAGE_SIZE : null)) throw new Error('API beklenen kural listesini döndürmedi.')
  data.items.forEach(validateRule)
  return data
}

export function validateRuleSave(data, expected, id = null) {
  validateRule(data)
  if ((id !== null && data.id !== id) || Object.entries(expected).some(([key, value]) => data[key] !== value)) {
    throw new Error('Kaydedilen kural doğrulanamadı. Listeyi yenileyip değerleri kontrol et.')
  }
  return data
}

const formatter = new Intl.NumberFormat('tr-TR', { maximumSignificantDigits: 15 })
export function describeRule(rule) {
  const measurement = rule.kind === 'log_count' ? `Son ${rule.window_seconds} saniyedeki ${rule.level} sayısı` : `${rule.metric_name} (${rule.metric_unit})`
  return `${measurement} ${RULE_OPERATORS[rule.operator]} ${formatter.format(rule.threshold)}`
}
