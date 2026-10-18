import { useEffect, useRef } from 'react'

const timeFormatter = new Intl.DateTimeFormat('tr-TR', {
  dateStyle: 'medium',
  timeStyle: 'long',
})

function DetailTime({ value }) {
  if (!value) return <span>Belirtilmemiş</span>
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return <span>Geçersiz zaman</span>
  return (
    <>
      <time dateTime={value}>{timeFormatter.format(date)}</time>
      <code className="detail-iso-time">{value}</code>
    </>
  )
}

export default function LogDetails({ log, onClose }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!log) {
      if (dialog.open) dialog.close()
      return
    }
    if (!dialog.open) dialog.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [log])

  const tags = log?.tags ?? {}
  const hasStackTrace = typeof log?.stack_trace === 'string' && log.stack_trace.trim().length > 0

  return (
    <dialog ref={dialogRef} className="log-detail-dialog" aria-labelledby="log-detail-title"
      aria-describedby="log-detail-description" onClose={(event) => {
        if (!event.currentTarget.open) onClose()
      }}>
      {log && (
        <>
          <header className="detail-header">
            <div>
              <p className="eyebrow">KAYIT #{log.id}</p>
              <h2 id="log-detail-title">Log detayı</h2>
            </div>
            <button className="secondary-button" type="button" autoFocus
              onClick={() => dialogRef.current.close()}>Kapat</button>
          </header>
          <div className="detail-content">
            <p id="log-detail-description" className="detail-intro">
              Seçtiğin kaydın ayrıntıları. Saatler tarayıcının yerel saatine göre gösterilir.
            </p>
            <dl className="detail-metadata">
              <div><dt>Servis</dt><dd>{log.service}</dd></div>
              <div><dt>Seviye</dt><dd><span className={`log-level level-${log.level}`}>{log.level}</span></dd></div>
              <div><dt>Olay zamanı</dt><dd><DetailTime value={log.timestamp} /></dd></div>
              <div><dt>Platformun aldığı zaman</dt><dd><DetailTime value={log.received_at} /></dd></div>
            </dl>

            <section className="detail-section" aria-labelledby="detail-message-title">
              <h3 id="detail-message-title">Tam mesaj</h3>
              <pre className="detail-text">{log.message}</pre>
            </section>
            <section className="detail-section" aria-labelledby="detail-tags-title">
              <h3 id="detail-tags-title">Etiketler</h3>
              {Object.keys(tags).length > 0
                ? <pre className="detail-text"><code>{JSON.stringify(tags, null, 2)}</code></pre>
                : <p className="detail-empty">Bu kayıtta ek etiket bulunmuyor.</p>}
            </section>
            <section className="detail-section" aria-labelledby="detail-stack-title">
              <h3 id="detail-stack-title">Hata izi <span>(stack_trace)</span></h3>
              {hasStackTrace
                ? <pre className="detail-text stack-trace"><code>{log.stack_trace}</code></pre>
                : <p className="detail-empty">Bu kayıtla birlikte stack_trace bilgisi gönderilmemiş.</p>}
            </section>
          </div>
        </>
      )}
    </dialog>
  )
}
