# Veri Alım API Sözleşmesi

## Uç noktalar

- POST /logs: Tek bir log kaydı kabul eder.
- POST /metrics: Tek bir metrik kaydı kabul eder.
- POST /logs/batch ve POST /metrics/batch: JSON dizisinde 1-100 kayıt kabul eder. Bir kayıt geçersizse bütün istek reddedilir. Başarılı 202 cevabı görev kimliği ve record_count içerir; worker paketi tek transaction içinde işler.

## Veri biçimi

İstek gövdesi JSON olmalıdır.
Content-Type: application/json kullanılmalıdır.

## Yanıtlar

- 202 Accepted: Veri doğrulandı ve işlenmek üzere kuyruğa alındı.
- 422 Unprocessable Entity: Gönderilen veri kurallara uymuyor.
- 503 Service Unavailable: Kuyruk veya veritabanına erişilemiyor. 202 cevabı yazmanın tamamlandığını belirtmez.

## Ortak kabul kuralları

- timestamp zorunludur; saat dilimi içeren ISO 8601 biçiminde olmalıdır.
- service zorunludur; boş veya yalnızca boşluklardan oluşamaz.
- tags gönderilirse JSON nesnesi olmalıdır; gönderilmezse {} kullanılır.
- id veritabanı tarafından oluşturulur.
- received_at API tarafından, verinin alındığı anda belirlenir.
- Tanımlanmayan ek alanlar reddedilir. tags içindeki sayılar da sonlu olmalıdır.

## Log kabul kuralları

- level zorunludur; INFO, WARN, ERROR veya FATAL olabilir.
- message zorunludur; boş veya yalnızca boşluklardan oluşamaz.
- stack_trace isteğe bağlıdır; metin veya null olabilir.

## Metrik kabul kuralları

- name ve unit zorunludur; boş veya yalnızca boşluklardan oluşamaz.
- value zorunludur; sonlu bir sayı olmalıdır.
- cpu_usage ve percent birlikte kullanıldığında value 0 ile 100 arasında olmalıdır.

## Okuma ve filtreleme

- GET /logs: service, level, q, tags, start, end, limit, offset.
- GET /metrics: service, name, unit, tags, start, end, limit, offset.
- start/end saat dilimi içeren zamanlardır; olay zamanı timestamp üzerinde dahil sınırlarla uygulanır.
- q kelime araması yapar. tags, JSON nesnesi biçiminde bir sorgu parametresidir.
- limit 1-200 (varsayılan 20), offset 0-100000 (varsayılan 0).
- Yanıt items, limit, offset, has_more ve next_offset alanlarını içerir.

## Alarm kuralları ve bildirimler

- GET /alert-rules: Kuralları listele (enabled, limit, offset).
- POST /alert-rules: Kural ekle; başarılı cevap 201.
- PATCH /alert-rules/{id}: Gönderilen alanları mevcut kuralla birleştirip doğrula; başarılı cevap 200.
- GET /alerts: Bildirimleri listele (service, status, rule_id, limit, offset).
- PATCH /alerts/{id}/acknowledge: Bildirimi görüldü olarak işaretle; başarılı cevap 200.
- Bulunmayan kayıt 404, aynı isimli kural 409, geçersiz kural 422 döndürür.

Kural alanları ve JSON örnekleri README.md içinde açıklanmıştır. Metrik kuralı yeni ölçümü karşılaştırır; log sayısı kuralı received_at üzerinden hareketli zaman penceresi kullanır. Servis belirtilmezse her servis ayrı değerlendirilir. Kural ve servis başına cooldown_seconds boyunca tekrar bildirim oluşturulmaz. Kural düzenlendiğinde bu bekleme sıfırlanır. Bildirim onaylamak otomatik çözülme anlamına gelmez.

## Sağlık

- GET /health: API sürecinin çalıştığını bildirir (200).
- GET /ready: Veritabanı şeması ve Redis erişimini kontrol eder (200/503); worker durumunu kontrol etmez.

Canlı OpenAPI tanımı /openapi.json, deneme ekranı /docs adresindedir.

## Görev takibi

GET /tasks/{task_id}: UUID biçimindeki kimlik için state, completed, successful döndürür. Durumlar PENDING, STARTED, RETRY, SUCCESS, FAILURE olabilir. Sonuçlar 24 saat saklanır. PENDING kimliğin var olduğunu kanıtlamaz; bilinmeyen veya süresi dolan kimlik için de dönebilir. Geçersiz kimlik 422, Redis erişim sorunu 503 döndürür. FAILURE durumunda genel açıklama verilir; hata ayrıntısı ve traceback worker loglarında kalır.
