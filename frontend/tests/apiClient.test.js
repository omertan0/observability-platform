import test from 'node:test'
import assert from 'node:assert/strict'
import { apiFetch, setSession, validateSession } from '../src/apiClient.js'

const session = { username: 'admin', csrf_token: 'c'.repeat(43), expires_at: '2026-10-25T12:00:00Z' }

test('session response rejects missing csrf and invalid expiration', () => {
  assert.equal(validateSession(session), session)
  for (const change of [{ csrf_token: '' }, { csrf_token: null }, { expires_at: 'wrong' }, { username: '' }]) {
    assert.throws(() => validateSession({ ...session, ...change }))
  }
})

test('mutations carry csrf and cookies while GET never receives csrf', async () => {
  setSession(session)
  const calls = []
  const transport = async (url, options) => { calls.push({ url, options }); return { status: 200 } }
  await apiFetch('/api/alert-rules', { method: 'POST', headers: { 'Content-Type': 'application/json' } }, transport)
  assert.equal(calls[0].options.headers.get('X-CSRF-Token'), session.csrf_token)
  assert.equal(calls[0].options.headers.get('Content-Type'), 'application/json')
  assert.equal(calls[0].options.credentials, 'same-origin')
  assert.equal(calls[0].options.redirect, 'error')
  await apiFetch('/api/logs', {}, transport)
  assert.equal(calls[1].options.headers.has('X-CSRF-Token'), false)
  setSession(null)
  await apiFetch('/api/auth/logout', { method: 'POST' }, transport)
  assert.equal(calls[2].options.headers.has('X-CSRF-Token'), false)
})

test('API helper rejects external origins before sending a token', async () => {
  let called = false
  const transport = async () => { called = true }
  await assert.rejects(apiFetch('https://example.com/api/logs', {}, transport))
  await assert.rejects(apiFetch('//example.com/api/logs', {}, transport))
  await assert.rejects(apiFetch('/api/\\example.com', {}, transport))
  assert.equal(called, false)
})
