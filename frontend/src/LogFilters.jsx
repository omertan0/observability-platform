export default function LogFilters({ filters, onChange, onApply, onClear, error, dirty }) {
  return (
    <form className="log-filters" onSubmit={onApply} aria-label="Log filtreleri">
      <div className="filter-fields">
        <label htmlFor="log-service-filter">
          Servis adı
          <input id="log-service-filter" name="service" type="text" maxLength={200}
            placeholder="Örn. payment-service" value={filters.service}
            onChange={(event) => onChange('service', event.target.value)} />
        </label>
        <label htmlFor="log-level-filter">
          Seviye
          <select id="log-level-filter" name="level" value={filters.level}
            onChange={(event) => onChange('level', event.target.value)}>
            <option value="">Tüm seviyeler</option>
            {['INFO', 'WARN', 'ERROR', 'FATAL'].map((level) => <option key={level} value={level}>{level}</option>)}
          </select>
        </label>
        <label className="filter-search" htmlFor="log-search-filter">
          Mesajda kelime
          <input id="log-search-filter" name="q" type="search" maxLength={500}
            placeholder="Örn. timeout" value={filters.q}
            onChange={(event) => onChange('q', event.target.value)} />
        </label>
        <label htmlFor="log-start-filter">
          Başlangıç zamanı
          <input id="log-start-filter" name="start" type="datetime-local" step="1" value={filters.start}
            onChange={(event) => onChange('start', event.target.value)} />
        </label>
        <label htmlFor="log-end-filter">
          Bitiş zamanı
          <input id="log-end-filter" name="end" type="datetime-local" step="1" value={filters.end}
            onChange={(event) => onChange('end', event.target.value)} />
        </label>
      </div>
      <div className="filter-actions">
        <button type="submit">Uygula</button>
        <button className="secondary-button" type="button" onClick={onClear}>Temizle</button>
        <p>Servis adı tam eşleşir, mesaj araması kelime bazlıdır. Zamanlar tarayıcının yerel saatindedir.</p>
      </div>
      {dirty && <p className="filter-notice" role="status">Değişiklikler henüz uygulanmadı.</p>}
      {error && <p className="filter-error" role="alert">{error}</p>}
    </form>
  )
}
