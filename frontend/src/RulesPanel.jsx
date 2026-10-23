import { useEffect, useRef, useState } from 'react'
import RuleEditor from './RuleEditor.jsx'
import { apiFetch } from './apiClient.js'
import { RULE_PAGE_SIZE, RULE_MAX_OFFSET, EMPTY_RULE, buildRulePayload, buildRuleQuery, ruleToDraft, validateRulePage, validateRuleSave, describeRule } from './ruleForm.js'

const EMPTY_RESULT = { query: null, items: [], loading: true, error: '', hasMore: false, nextOffset: null }
const dateFormatter = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'short', timeStyle: 'medium' })

export default function RulesPanel() {
  const [offset, setOffset] = useState(0)
  const [result, setResult] = useState(EMPTY_RESULT)
  const [refreshKey, setRefreshKey] = useState(0)
  const [editor, setEditor] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const mutationRef = useRef(null)
  const headingRef = useRef(null)
  const editorHeadingRef = useRef(null)
  const noticeRef = useRef(null)
  const query = buildRuleQuery(offset)
  const { items: rules, loading, error, hasMore, nextOffset } = result.query === query ? result : EMPTY_RESULT
  const editorKey = editor ? editor.id ?? 'new' : 'closed'

  useEffect(() => { if (editorKey !== 'closed') editorHeadingRef.current?.focus() }, [editorKey])
  useEffect(() => { if (notice) noticeRef.current?.focus() }, [notice])
  useEffect(() => () => { const controller = mutationRef.current; mutationRef.current = null; controller?.abort() }, [])

  useEffect(() => {
    if (busy) return
    let active = true
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    async function loadRules() {
      setResult((previous) => ({ ...(previous.query === query ? previous : EMPTY_RESULT), query, loading: true, error: '' }))
      try {
        const response = await apiFetch(`/api/alert-rules?${query}`, { signal: controller.signal })
        if (!response.ok) throw new Error(`Kurallar alınamadı (HTTP ${response.status}). Servisleri kontrol edip yeniden dene.`)
        const data = validateRulePage(await response.json(), offset)
        if (active) setResult({ query, items: data.items, loading: false, error: '', hasMore: data.has_more, nextOffset: data.next_offset })
      } catch (cause) {
        if (active) setResult((previous) => ({ ...previous, query, loading: false,
          error: controller.signal.aborted ? 'Kural isteği zaman aşımına uğradı. Yeniden dene.' : cause instanceof Error ? cause.message : 'Kurallar yüklenemedi.' }))
      } finally { clearTimeout(timeout) }
    }
    loadRules()
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [query, offset, refreshKey, busy])

  function openEditor(rule = null) {
    setNotice(null)
    setEditor({ id: rule?.id ?? null, draft: rule ? ruleToDraft(rule) : { ...EMPTY_RULE } })
  }

  function changeField(key, value) {
    setEditor((previous) => {
      const draft = { ...previous.draft, [key]: value }
      if (key === 'kind' && value === 'log_count' && !['gt', 'gte'].includes(draft.operator)) draft.operator = 'gt'
      return { ...previous, draft }
    })
  }

  async function saveRule(payload, id, closeEditor) {
    if (mutationRef.current) return
    const controller = new AbortController()
    mutationRef.current = controller
    setBusy(true)
    setNotice(null)
    const timeout = setTimeout(() => controller.abort(), 15000)
    try {
      const response = await apiFetch(id === null ? '/api/alert-rules' : `/api/alert-rules/${id}`, {
        method: id === null ? 'POST' : 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.signal,
      })
      if (!response.ok) throw new Error(response.status === 409 ? 'Bu isimde bir kural zaten var. İsmini değiştir veya listedeki kuralı düzenle.'
        : response.status === 422 ? 'Kural alanları kabul edilmedi. Değerleri kontrol et.'
        : response.status === 404 ? 'Kural artık bulunamıyor. Listeyi yenile.'
        : `İşlem doğrulanamadı (HTTP ${response.status}). Listeyi yenileyip kontrol et.`)
      const saved = validateRuleSave(await response.json(), payload, id)
      if (mutationRef.current !== controller) return
      if (closeEditor) setEditor(null)
      if (id === null) setOffset(0)
      setNotice({ kind: 'success', message: `#${saved.id} · ${saved.name}: ${saved.enabled ? 'etkin' : 'kapalı'} olarak kaydedildi. Ayarlar sonraki gelen kayıtlarda uygulanır.` })
    } catch (cause) {
      if (mutationRef.current === controller) setNotice({ kind: 'error', message: controller.signal.aborted
        ? 'İstek zaman aşımına uğradı. İşlem kaydedilmiş olabilir; tekrar oluşturmadan önce listeyi yenileyip kontrol et.'
        : cause instanceof TypeError ? 'API ile iletişim kurulamadı. İşlem kaydedilmiş olabilir; listeyi yenileyip kontrol et.'
        : cause instanceof SyntaxError ? 'API yanıtı okunamadı. İşlem kaydedilmiş olabilir; listeyi yenileyip kontrol et.'
        : cause instanceof Error ? cause.message : 'İşlem doğrulanamadı. Listeyi yenileyip kontrol et.' })
    } finally {
      clearTimeout(timeout)
      if (mutationRef.current === controller) { mutationRef.current = null; setBusy(false); setRefreshKey((value) => value + 1) }
    }
  }

  function submitRule(event) {
    event.preventDefault()
    try { saveRule(buildRulePayload(editor.draft), editor.id, true) }
    catch (cause) { setNotice({ kind: 'error', message: cause.message }) }
  }

  return <section className="logs-panel rules-panel" aria-labelledby="rules-title">
    <div className="logs-heading">
      <div><p className="eyebrow">ALARM AYARLARI</p><h2 id="rules-title" ref={headingRef} tabIndex={-1}>Alarm kuralları</h2>
        <p className="logs-description">Yeni kural oluştur, düzenle veya açıp kapat. Değişiklikler tekrar bekleme durumunu sıfırlar ve sonraki gelen kayıtlara uygulanır; önceki kayıtlar yeniden değerlendirilmez.</p></div>
      <div className="rule-actions"><button type="button" className="secondary-button" disabled={loading || busy} onClick={() => setRefreshKey((value) => value + 1)}>Kuralları yenile</button>
        <button type="button" disabled={busy || editor !== null} onClick={() => openEditor()}>Yeni kural</button></div>
    </div>
    {notice && <p ref={noticeRef} tabIndex={-1} role={notice.kind === 'error' ? 'alert' : 'status'} className={`alert-notice ${notice.kind}`}>{notice.message}</p>}
    {editor && <RuleEditor editor={editor} busy={busy} headingRef={editorHeadingRef} onChange={changeField} onSubmit={submitRule}
      onCancel={() => { setEditor(null); setNotice(null); headingRef.current?.focus() }} />}
    <div aria-busy={loading}>
      {error && <p className="logs-feedback connection-error" role="alert">{error}{rules.length > 0 && ' Önceki liste gösteriliyor; güncelliği doğrulanamadı.'}</p>}
      {loading && rules.length === 0 && <p className="logs-feedback" role="status">Kurallar yükleniyor…</p>}
      {!loading && !error && rules.length === 0 && <p className="logs-feedback">{offset > 0 ? 'Bu sayfada kural yok. Önceki veya ilk sayfaya dön.' : 'Henüz alarm kuralı yok. Yeni kural düğmesiyle oluşturabilirsin.'}</p>}
      {rules.length > 0 && <div className="logs-scroll" role="region" aria-label="Alarm kuralları tablosu" tabIndex={0}>
        <table className="logs-table rules-table"><caption className="sr-only">Alarm kuralları, koşulları ve etkinlik durumları</caption>
          <thead><tr><th scope="col">KURAL</th><th scope="col">KOŞUL VE KAPSAM</th><th scope="col">DURUM</th><th scope="col">İŞLEMLER</th></tr></thead>
          <tbody>{rules.map((rule) => <tr key={rule.id}>
            <td className="alert-description"><strong>{rule.name}</strong><span className="alert-kind">#{rule.id} · {rule.kind === 'log_count' ? 'Log sayısı' : 'Metrik eşiği'}</span></td>
            <td className="rule-condition"><p>{describeRule(rule)}</p><small>{rule.service ?? 'Tüm servisler · her biri ayrı'}<br />Tekrar bekleme: {rule.cooldown_seconds} saniye</small></td>
            <td><span className={`status ${rule.enabled ? 'ready' : ''}`}>{rule.enabled ? 'Etkin' : 'Kapalı'}</span><time className="alert-ack-time" dateTime={rule.updated_at}>{dateFormatter.format(new Date(rule.updated_at))}</time></td>
            <td><div className="rule-actions"><button type="button" className="secondary-button log-detail-button" disabled={busy || editor !== null} aria-label={`${rule.name} kuralını düzenle`} onClick={() => openEditor(rule)}>Düzenle</button>
              <button type="button" className="secondary-button log-detail-button" disabled={busy || editor !== null} aria-label={`${rule.name} kuralını ${rule.enabled ? 'kapat' : 'aç'}`} onClick={() => saveRule({ enabled: !rule.enabled }, rule.id, false)}>{rule.enabled ? 'Kapat' : 'Aç'}</button></div></td>
          </tr>)}</tbody>
        </table>
      </div>}
    </div>
    <div className="logs-footer"><p role="status">Sayfa {offset / RULE_PAGE_SIZE + 1} · {loading ? 'Yükleniyor…' : error ? 'Güncel liste alınamadı' : `${rules.length} kural`}</p>
      <nav className="pagination" aria-label="Kural sayfaları">
        {offset > 0 && <button className="secondary-button" disabled={loading || busy || editor !== null} onClick={() => setOffset(0)}>İlk sayfa</button>}
        <button className="secondary-button" disabled={loading || busy || editor !== null || offset === 0} onClick={() => setOffset((value) => value - RULE_PAGE_SIZE)}>Önceki</button>
        <button className="secondary-button" disabled={loading || busy || editor !== null || !!error || !hasMore || nextOffset > RULE_MAX_OFFSET} onClick={() => setOffset(nextOffset)}>Sonraki</button>
      </nav>
      {hasMore && nextOffset > RULE_MAX_OFFSET && <p className="pagination-note">API sayfalama sınırına ulaşıldı.</p>}
    </div>
  </section>
}
