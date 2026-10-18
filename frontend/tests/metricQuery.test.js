import assert from 'node:assert/strict'
import test from 'node:test'
import { buildMetricQuery, metricPoints, timeDomain, metricWindow, metricTicks, metricTickLabel, metricType, formatMetricValue } from '../src/metricQuery.js'

const metric = (id, timestamp, value = 50) => ({ id, timestamp, value, service: 'payment-service', name: 'cpu_usage', unit: 'percent' })
const response = (items) => ({ items, limit: 100, offset: 0, has_more: false })

test('CPU query requires one service and preserves special characters', () => {
  const query = new URLSearchParams(buildMetricQuery('  ödeme & API  '))
  assert.equal(query.get('service'), 'ödeme & API')
  assert.equal(query.get('name'), 'cpu_usage')
  assert.equal(query.get('unit'), 'percent')
  assert.equal(query.get('limit'), '100')
  assert.throws(() => buildMetricQuery('  '))
  assert.throws(() => buildMetricQuery('a'.repeat(201)))
})

test('chart sorts actual instants and preserves zero, duplicate times and input', () => {
  const items = [metric(3, '2026-10-18T15:00:00Z', 0), metric(2, '2026-10-18T14:00:00Z'), metric(1, '2026-10-18T17:00:00+03:00')]
  const points = metricPoints(response(items), 'payment-service')
  assert.deepEqual(points.map((point) => point.id), [1, 2, 3])
  assert.equal(points.at(-1).value, 0)
  assert.equal(points[0].time, points[1].time)
  assert.equal(points[2].time - points[1].time, 3600000)
  assert.deepEqual(items.map((point) => point.id), [3, 2, 1])
})

test('wrong series, invalid data and unexpected pages are rejected', () => {
  const original = metric(1, '2026-10-18T14:00:00Z')
  for (const change of [{ service: 'other-service' }, { name: 'latency' }, { unit: 'ms' }, { value: null }, { value: Infinity }, { value: -1 }, { value: 101 }, { timestamp: 'invalid' }]) {
    assert.throws(() => metricPoints(response([{ ...original, ...change }]), 'payment-service'))
  }
  assert.throws(() => metricPoints({ ...response([]), offset: 100 }, 'payment-service'))
  assert.deepEqual(metricPoints(response([]), 'payment-service'), [])
})

test('time axis uses elapsed time and expands a single instant without inventing points', () => {
  const points = metricPoints(response([metric(2, '2026-10-18T14:03:00Z'), metric(1, '2026-10-18T14:00:00Z')]), 'payment-service')
  assert.equal(timeDomain(points)[1] - timeDomain(points)[0], 180000)
  const one = [points[0]]
  assert.deepEqual(timeDomain(one), [one[0].time - 30000, one[0].time + 30000])
  assert.equal(one.length, 1)
})

test('recent window separates minute-spaced samples from week-old history and keeps duplicate instants', () => {
  // Kullanıcının bildirdiği dağılım: hafta önce iki örnek, bugün birkaç dakika aralıklı dört örnek.
  const points = metricPoints(response([
    metric(6, '2026-10-18T19:53:00Z', 98), metric(5, '2026-10-18T19:46:00Z', 58),
    metric(4, '2026-10-18T19:45:00Z', 51), metric(3, '2026-10-18T19:45:00Z', 45),
    metric(2, '2026-10-11T16:49:27Z', 90), metric(1, '2026-10-10T10:30:00Z', 87.5),
  ]), 'payment-service')
  const shown = metricWindow(points, '1h')
  assert.deepEqual(shown.map((point) => point.id), [3, 4, 5, 6])
  assert.equal(timeDomain(shown)[1] - timeDomain(shown)[0], 8 * 60000)
  assert.equal(shown[0].time, shown[1].time)
  assert.equal(metricWindow(points, 'all').length, 6)
  assert.equal(points.length, 6)
})

test('window anchors to last recorded event, includes its boundary and handles an empty series', () => {
  const points = metricPoints(response([
    metric(3, '2026-10-10T13:00:00Z'), metric(2, '2026-10-10T12:00:00Z'), metric(1, '2026-10-09T13:00:00Z'),
  ]), 'payment-service')
  assert.deepEqual(metricWindow(points, '1h').map((point) => point.id), [2, 3])
  assert.equal(metricWindow(points, '24h').length, 3)
  assert.deepEqual(metricWindow([], '1h'), [])
  assert.throws(() => metricWindow(points, 'invalid'))
})

test('short spans keep distinct second labels and narrow charts receive fewer ticks', () => {
  const points = metricPoints(response([metric(2, '2026-10-18T14:00:30Z'), metric(1, '2026-10-18T14:00:00Z')]), 'payment-service')
  const wideTicks = metricTicks(points, 1000)
  const narrowTicks = metricTicks(points, 320)
  assert.equal(narrowTicks.length, 2)
  assert.equal(wideTicks.length, 6)
  assert.equal(new Set(wideTicks.map((value) => metricTickLabel(value, 30000).time)).size, wideTicks.length)
  assert.equal(wideTicks[0], points[0].time)
  assert.equal(wideTicks.at(-1), points.at(-1).time)
  const instant = points[0].time
  assert.notEqual(metricTickLabel(instant, 1000).time, metricTickLabel(instant + 250, 1000).time)
})

test('metric selection requests the matching name and unit and changes the live query', () => {
  const cpu = buildMetricQuery('payment-service', 'cpu')
  const memory = buildMetricQuery('payment-service', 'memory')
  const responseTime = buildMetricQuery('payment-service', 'response')
  assert.notEqual(cpu, memory)
  assert.notEqual(cpu, responseTime)
  assert.equal(new URLSearchParams(memory).get('name'), 'memory_usage')
  assert.equal(new URLSearchParams(memory).get('unit'), 'percent')
  assert.equal(new URLSearchParams(responseTime).get('name'), 'response_time')
  assert.equal(new URLSearchParams(responseTime).get('unit'), 'ms')
  assert.throws(() => buildMetricQuery('payment-service', 'invalid'))
  assert.throws(() => metricType('invalid'))
})

test('response times above 100 are valid while percentages and mixed units remain checked', () => {
  const sample = { ...metric(1, '2026-10-18T14:00:00Z', 420.5), name: 'response_time', unit: 'ms' }
  assert.equal(metricPoints(response([sample]), 'payment-service', 'response')[0].value, 420.5)
  assert.equal(metricPoints(response([{ ...sample, value: 0 }]), 'payment-service', 'response')[0].value, 0)
  assert.throws(() => metricPoints(response([{ ...sample, unit: 'seconds' }]), 'payment-service', 'response'))
  assert.throws(() => metricPoints(response([{ ...sample, value: -1 }]), 'payment-service', 'response'))
  const memory = { ...sample, name: 'memory_usage', unit: 'percent', value: 64.2 }
  assert.equal(metricPoints(response([memory]), 'payment-service', 'memory')[0].value, 64.2)
  assert.throws(() => metricPoints(response([{ ...memory, value: 101 }]), 'payment-service', 'memory'))
  assert.throws(() => metricPoints(response([memory]), 'payment-service', 'response'))
  assert.throws(() => metricPoints(response([sample]), 'payment-service', 'memory'))
})

test('summary and tooltip values retain the selected unit including zero', () => {
  assert.equal(formatMetricValue(64.2, 'memory'), '%64,2')
  assert.equal(formatMetricValue(420.5, 'response'), '420,5 ms')
  assert.equal(formatMetricValue(0, 'response'), '0 ms')
  assert.equal(formatMetricValue(0, 'cpu'), '%0')
})
