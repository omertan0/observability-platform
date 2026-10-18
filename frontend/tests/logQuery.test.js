import assert from 'node:assert/strict'
import test from 'node:test'
import { buildLogFilters, buildLogPageQuery, EMPTY_FILTERS } from '../src/logQuery.js'

process.env.TZ = 'Europe/Istanbul'

test('Filtrelerde boş alanlar atlanır, Türkçe ve URL özel karakterleri korunur', () => {
  const query = buildLogFilters({ ...EMPTY_FILTERS, service: ' ödeme&api ', q: ' timeout + "ödeme" ' })
  const params = new URLSearchParams(query)
  assert.equal(params.get('service'), 'ödeme&api')
  assert.equal(params.get('q'), 'timeout + "ödeme"')
  assert.equal(params.has('level'), false)
  assert.equal(params.size, 2)
  assert.equal(buildLogFilters(EMPTY_FILTERS), '')
})

test('Yerel zaman, saniyeleri ve aralık sınırlarını koruyarak UTC olarak gönderilir', () => {
  const query = buildLogFilters({ ...EMPTY_FILTERS, start: '2026-10-18T14:05:06', end: '2026-10-18T14:05:07' })
  const params = new URLSearchParams(query)
  assert.equal(params.get('start'), '2026-10-18T11:05:06.000Z')
  assert.equal(params.get('end'), '2026-10-18T11:05:07.000Z')
  assert.doesNotThrow(() => buildLogFilters({ ...EMPTY_FILTERS, start: '2026-10-18T14:00', end: '2026-10-18T14:00' }))
})

test('Ters zaman aralığı ve geçersiz tarih istek oluşturulmadan reddedilir', () => {
  assert.throws(() => buildLogFilters({ ...EMPTY_FILTERS, start: '2026-10-18T15:00', end: '2026-10-18T14:00' }), /Başlangıç/)
  assert.throws(() => buildLogFilters({ ...EMPTY_FILTERS, start: 'geçersiz' }), /Geçerli/)
})

test('Sayfalama filtreleri korur ve API sınırını aşan sayfaları reddeder', () => {
  const filters = buildLogFilters({ ...EMPTY_FILTERS, service: 'payment-service', level: 'ERROR' })
  const query = new URLSearchParams(buildLogPageQuery(filters, 20))
  assert.equal(query.get('service'), 'payment-service')
  assert.equal(query.get('level'), 'ERROR')
  assert.equal(query.get('limit'), '20')
  assert.equal(query.get('offset'), '20')
  for (const invalid of [-20, 1, 100020, NaN, 20.5]) {
    assert.throws(() => buildLogPageQuery(filters, invalid), /Geçersiz/)
  }
})
