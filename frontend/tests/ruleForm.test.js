import assert from 'node:assert/strict'
import test from 'node:test'
import { EMPTY_RULE, buildRulePayload, ruleToDraft, buildRuleQuery, validateRulePage, validateRuleSave, describeRule } from '../src/ruleForm.js'

const draft = { ...EMPTY_RULE, name: ' CPU eşiği ', service: ' ', threshold: '85.5', cooldown_seconds: '0' }
const record = { ...buildRulePayload(draft), id: 1, created_at: '2026-10-18T20:00:00Z', updated_at: '2026-10-18T20:00:00Z' }

test('metric rule trims text, scopes blank service to all and clears log-only fields', () => {
  const payload = buildRulePayload({ ...draft, level: 'ERROR', window_seconds: 'invalid' })
  assert.equal(payload.name, 'CPU eşiği')
  assert.equal(payload.service, null)
  assert.equal(payload.metric_name, 'cpu_usage')
  assert.equal(payload.metric_unit, 'percent')
  assert.equal(payload.level, null)
  assert.equal(payload.threshold, 85.5)
  assert.equal(payload.cooldown_seconds, 0)
  assert.equal(payload.window_seconds, 300)
})

test('log rule clears metric fields and accepts zero count and inclusive threshold', () => {
  const payload = buildRulePayload({ ...draft, kind: 'log_count', operator: 'gte', threshold: '0', window_seconds: '60' })
  assert.equal(payload.metric_name, null)
  assert.equal(payload.metric_unit, null)
  assert.equal(payload.level, 'ERROR')
  assert.equal(payload.threshold, 0)
  assert.equal(payload.window_seconds, 60)
  assert.equal(payload.operator, 'gte')
  assert.throws(() => buildRulePayload({ ...draft, kind: 'log_count', operator: 'lt' }))
  assert.throws(() => buildRulePayload({ ...draft, kind: 'log_count', threshold: '1.5' }))
  assert.throws(() => buildRulePayload({ ...draft, kind: 'log_count', threshold: '-1' }))
})

test('missing numbers never become zero and invalid numeric limits are rejected', () => {
  for (const threshold of ['', ' ', 'NaN', 'Infinity', 'not a number']) assert.throws(() => buildRulePayload({ ...draft, threshold }))
  for (const cooldown_seconds of ['', '-1', '1.5', '86401']) assert.throws(() => buildRulePayload({ ...draft, cooldown_seconds }))
  for (const window_seconds of ['', '0', '0.5', '86401']) assert.throws(() => buildRulePayload({ ...draft, kind: 'log_count', window_seconds }))
  for (const changes of [{ name: ' ' }, { service: 'a'.repeat(201) }, { metric_unit: 'a'.repeat(51) }, { enabled: 'false' }, { kind: 'invalid' }]) {
    assert.throws(() => buildRulePayload({ ...draft, ...changes }))
  }
  assert.equal(buildRulePayload({ ...draft, threshold: '-0.001' }).threshold, -0.001)
})

test('editing preserves zero values, disabled state and nullable fields without truthy defaults', () => {
  const edited = { ...record, threshold: 0, cooldown_seconds: 0, enabled: false }
  const result = buildRulePayload(ruleToDraft(edited))
  assert.equal(result.threshold, 0)
  assert.equal(result.cooldown_seconds, 0)
  assert.equal(result.enabled, false)
  assert.equal(result.service, null)
  assert.equal(result.level, null)
})

test('save confirmation requires the requested id and values, including enabled-only patches', () => {
  assert.equal(validateRuleSave(record, buildRulePayload(draft)), record)
  const disabled = { ...record, enabled: false }
  assert.equal(validateRuleSave(disabled, { enabled: false }, 1), disabled)
  assert.throws(() => validateRuleSave(record, { enabled: false }, 1))
  assert.throws(() => validateRuleSave(record, { threshold: 85.5 }, 2))
  assert.throws(() => validateRuleSave({ ...record, window_seconds: 0 }, {}, 1))
  assert.throws(() => validateRuleSave({ ...record, updated_at: 'invalid' }, {}, 1))
})

test('rule pages enforce API bounds and validate every listed rule', () => {
  assert.equal(new URLSearchParams(buildRuleQuery(20)).get('offset'), '20')
  assert.equal(new URLSearchParams(buildRuleQuery(100000)).get('limit'), '20')
  for (const offset of [-20, 1, 100020]) assert.throws(() => buildRuleQuery(offset))
  const page = { items: [record], limit: 20, offset: 0, has_more: false, next_offset: null }
  assert.equal(validateRulePage(page, 0), page)
  assert.throws(() => validateRulePage(page, 20))
  assert.throws(() => validateRulePage({ ...page, next_offset: 20 }, 0))
  assert.throws(() => validateRulePage({ ...page, items: [{ ...record, level: 'ERROR' }] }, 0))
})

test('rule description includes the log window and does not round tiny thresholds to zero', () => {
  assert.equal(describeRule({ ...record, threshold: 0.00001 }), 'cpu_usage (percent) > 0,00001')
  assert.equal(describeRule({ ...record, kind: 'log_count', level: 'WARN', window_seconds: 60, threshold: 10, operator: 'gte' }), 'Son 60 saniyedeki WARN sayısı ≥ 10')
})
