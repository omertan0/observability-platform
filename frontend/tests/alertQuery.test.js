import assert from 'node:assert/strict'
import test from 'node:test'
import { ALERT_PAGE_SIZE, ALERT_MAX_OFFSET, EMPTY_ALERT_FILTERS, buildAlertFilters, buildAlertPageQuery, validateAlertPage, validateAcknowledgment } from '../src/alertQuery.js'

const sample = { id: 1, rule_name: 'CPU eşiği', service: 'payment-service', message: 'cpu_usage (percent) = 98; eşik > 85.',
  kind: 'metric_threshold', status: 'open', triggered_at: '2026-10-18T19:48:05Z', acknowledged_at: null }
const page = { items: [sample], limit: ALERT_PAGE_SIZE, offset: 0, has_more: false, next_offset: null }

test('alarm filters distinguish all, unseen and acknowledged records and encode service names', () => {
  assert.equal(buildAlertFilters(EMPTY_ALERT_FILTERS), 'status=open')
  assert.equal(buildAlertFilters({ service: ' ', status: '' }), '')
  const filters = new URLSearchParams(buildAlertFilters({ service: ' ödeme & API ', status: 'acknowledged' }))
  assert.equal(filters.get('service'), 'ödeme & API')
  assert.equal(filters.get('status'), 'acknowledged')
  assert.throws(() => buildAlertFilters({ service: '', status: 'resolved' }))
  assert.throws(() => buildAlertFilters({ service: 'a'.repeat(201), status: '' }))
})

test('alarm pagination retains filters and enforces API bounds', () => {
  const filters = buildAlertFilters({ service: 'payment-service', status: 'open' })
  const query = new URLSearchParams(buildAlertPageQuery(filters, 20))
  assert.equal(query.get('service'), 'payment-service')
  assert.equal(query.get('status'), 'open')
  assert.equal(query.get('offset'), '20')
  assert.equal(query.get('limit'), '20')
  assert.equal(new URLSearchParams(buildAlertPageQuery(filters, ALERT_MAX_OFFSET)).get('offset'), '100000')
  for (const offset of [-20, 1, 20.5, ALERT_MAX_OFFSET + 20]) assert.throws(() => buildAlertPageQuery(filters, offset))
})

test('alarm pages reject malformed metadata, unsupported statuses and invalid dates', () => {
  assert.equal(validateAlertPage(page, 0), page)
  assert.equal(validateAlertPage({ ...page, items: [] }, 0).items.length, 0)
  for (const changes of [{ offset: 20 }, { next_offset: 20 }, { has_more: true, next_offset: 40 }, { limit: 200 }]) {
    assert.throws(() => validateAlertPage({ ...page, ...changes }, 0))
  }
  for (const changes of [{ status: 'resolved' }, { triggered_at: 'bad date' }, { acknowledged_at: 'bad date' }, { status: 'acknowledged' }, { kind: 'unknown' }, { id: 0 }]) {
    assert.throws(() => validateAlertPage({ ...page, items: [{ ...sample, ...changes }] }, 0))
  }
})

test('acknowledgment requires the requested alarm and a confirmed server timestamp', () => {
  const acknowledged = { ...sample, status: 'acknowledged', acknowledged_at: '2026-10-18T20:30:00Z' }
  assert.equal(validateAcknowledgment(acknowledged, 1), acknowledged)
  validateAlertPage({ ...page, items: [acknowledged] }, 0)
  for (const data of [sample, { ...acknowledged, id: 2 }, { ...acknowledged, acknowledged_at: null }, null]) {
    assert.throws(() => validateAcknowledgment(data, 1))
  }
})
