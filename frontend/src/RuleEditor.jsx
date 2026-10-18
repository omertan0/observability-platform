import { RULE_LEVELS, RULE_OPERATORS } from './ruleForm.js'
import { METRIC_TYPES } from './metricQuery.js'

export default function RuleEditor({ editor, onChange, onSubmit, onCancel, busy, headingRef }) {
  const draft = editor.draft
  const log = draft.kind === 'log_count'
  const field = (key) => ({ value: draft[key], onChange: (event) => onChange(key, event.target.value) })
  return <form className="rule-editor" onSubmit={onSubmit} aria-labelledby="rule-editor-title">
    <h3 id="rule-editor-title" tabIndex={-1} ref={headingRef}>{editor.id === null ? 'Yeni alarm kuralı' : `Kuralı düzenle · #${editor.id}`}</h3>
    <fieldset disabled={busy}>
      <legend className="sr-only">Kural alanları</legend>
      <div className="rule-fields">
        <label>Kural adı<input required maxLength={200} {...field('name')} /></label>
        <label>Kural türü<select {...field('kind')}><option value="metric_threshold">Metrik eşiği</option><option value="log_count">Log sayısı</option></select></label>
        <label>Servis adı<input maxLength={200} placeholder="Boş bırak: tüm servisler ayrı ayrı" {...field('service')} /></label>
        {log ? <>
          <label>Log seviyesi<select {...field('level')}>{RULE_LEVELS.map((level) => <option key={level}>{level}</option>)}</select></label>
          <label>Zaman penceresi (saniye)<input type="number" min="1" max="86400" step="1" required {...field('window_seconds')} /></label>
        </> : <>
          <label>Metrik adı<input required maxLength={200} list="rule-metric-names" {...field('metric_name')} /></label>
          <datalist id="rule-metric-names">{METRIC_TYPES.map((type) => <option key={type.key} value={type.name}>{type.label}</option>)}</datalist>
          <label>Metrik birimi<input required maxLength={50} list="rule-metric-units" {...field('metric_unit')} /></label>
          <datalist id="rule-metric-units"><option value="percent" /><option value="ms" /></datalist>
        </>}
        <label>Karşılaştırma<select {...field('operator')}>{Object.entries(RULE_OPERATORS).filter(([key]) => !log || ['gt', 'gte'].includes(key)).map(([key, symbol]) => <option key={key} value={key}>{symbol} {({ gt: 'Büyük', gte: 'Büyük veya eşit', lt: 'Küçük', lte: 'Küçük veya eşit' })[key]}</option>)}</select></label>
        <label>Eşik<input type="number" required step={log ? '1' : 'any'} min={log ? '0' : undefined} {...field('threshold')} /></label>
        <label>Tekrar bekleme (saniye)<input type="number" min="0" max="86400" step="1" required {...field('cooldown_seconds')} /></label>
      </div>
      <label className="rule-enabled"><input type="checkbox" checked={draft.enabled} onChange={(event) => onChange('enabled', event.target.checked)} />Kural etkin</label>
      <p className="rule-help">Servis boşsa her servis ayrı değerlendirilir. Metrik adı ve birimi gönderilen ölçümle tam eşleşmelidir. Zaman penceresi log sayısını belirler; tekrar bekleme aynı kural ve servis için iki alarm arasındaki en kısa süredir. 300 saniye = 5 dakika.</p>
      <div className="pagination"><button type="submit">{busy ? 'Kaydediliyor…' : editor.id === null ? 'Kural oluştur' : 'Değişiklikleri kaydet'}</button><button type="button" className="secondary-button" onClick={onCancel}>Vazgeç</button></div>
    </fieldset>
  </form>
}
