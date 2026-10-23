# Veri Alım API Sözleşmesi

## Erişim — sürüm 0.6.0

`GET /health` dışındaki okuma/izleme ve yönetim yolları yönetici oturumu gerektirir. `POST /auth/login`, JSON username/password ve `X-Requested-With: observability` alır; HttpOnly/SameSite=Strict çerezi ile sekiz saatlik Redis oturumu oluşturur. Aynı IP için 60 saniyede 10 giriş denemesi sınırı vardır. `GET /auth/session`, username/csrf_token/expires_at döndürür. Çerezle yapılan POST/PATCH/PUT/DELETE isteklerinde `X-CSRF-Token` ve izin verilen Origin kontrolü uygulanır. `POST /auth/logout` oturumu iptal eder.

Uygulamalar `Authorization: Bearer <INGEST_API_KEY>` kullanabilir. Bu anahtar yalnızca POST /logs, /metrics, /logs/batch, /metrics/batch ile GET /tasks/{id} ve GET /ready için geçerlidir. Listeleme, alarm/kural yönetimi, docs veya SSE erişimi vermez. Gönderilen Bearer başlığı çerezden önce değerlendirilir. Bir anahtarla tüm servis adlarına veri gönderilebilir; servis başına veya görev sahibi başına ayrı yetkilendirme uygulanmaz. Görev durumu yanıtı kaydın içeriğini içermez.

401 giriş/anahtar eksik veya geçersiz, 403 yetki/CSRF/kaynak kontrolü başarısız, 429 giriş sınırı, 413 büyük giriş gövdesi, 503 erişim ayarları veya oturum servisi hazır değil anlamına gelir. Giriş gövdesi 4 KiB ile sınırlandırılır. Yetkilendirme doğrulamadan önce çalışır. /docs ve /openapi.json da korumalıdır; OpenAPI güvenlik şemaları cookie+CSRF ve sınırlı Bearer seçeneklerini gösterir.

SSE bağlantısı açıkken oturum döngü başlarında yeniden doğrulanır. Geçersiz/iptal edilmiş oturum için `event: auth_expired`, `data: {"status":"unauthorized"}` gönderilir ve bağlantı kapanır. Oturum Redis'ine erişilemiyorsa stream_status/unavailable gönderilir, veri sorgusu yapılmaz. Panel auth_expired veya 401 aldığında giriş ekranına döner. Yerel HTTP çerezi Secure=false; HTTPS dağıtımında SESSION_COOKIE_SECURE=true yapılandırılmalıdır.

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

## Canlı log akışı

- GET /stream/logs: `text/event-stream` biçiminde açık SSE bağlantısı.
- Aynı `service`, `level`, `q`, `tags`, `start`, `end` filtrelerini kabul eder. Uygunsuz filtreler akış başlıkları gönderilmeden önce 422 ile reddedilir. Paneldeki canlı görünüm ilk sayfadır; akış `limit`/`offset` ile sayfalanmaz.
- `retry: 3000`: Bağlantı kaybında EventSource yeniden bağlanmayı yaklaşık 3 saniye sonra dener.
- `logs_changed`: İlk bağlantıda ve seçilen filtrelere uyan ilk 21 logun kimlik/zaman listesi değiştiğinde gönderilir. JSON verisi `revision` alanını taşır; `id` aynı özet değeridir. İstemci güncel satırları aynı filtrelerle GET /logs?limit=20&offset=0 üzerinden yeniden alır. Fazladan bir satır, `has_more` durumunun değişmesini de bildirir.
- `stream_status`: Akış açıkken DB sorgusu başarısızsa `{"status":"unavailable"}` gönderilir. Bu durumda HTTP başlıkları zaten gönderildiğinden HTTP durumu 200 kalır. DB tekrar erişilebilir olunca değişiklik olmasa bile yeni `logs_changed` ile eşitleme yapılır.
- Yaklaşık 15 saniyede bir `: keepalive` yorumu gönderilir; bu bir uygulama olayı değildir.
- Sunucu her açık akış için iki saniyede bir veritabanını kontrol eder. Tarayıcı periyodik GET göndermez; değişiklik bildirimi alırsa listeyi tekrar okur. Bu sürüm, çok sayıda panel bağlantısı için ortak bildirim dağıtımı henüz kullanmaz.
- Yalnızca commit edilmiş kayıtlar görülür. Değişiklik kontrolü tabloyla aynı `timestamp DESC, id DESC` sıralamasındaki filtrelenmiş 20 kayıt ve bir sonraki kayıtla sınırlıdır. Bu pencereye girmeyen eski bir kayıt mevcut görünümü değiştirmez. Filtreler genel son 20 kayıt listesinden bağımsızdır.
- Yeniden bağlantıda Last-Event-ID geçmiş olayların tekrar oynatılması için kullanılmaz; güncel listeyi yeniden okutan ilk bildirim daima gönderilir. Her log için ayrı olay veya kalıcı olay geçmişi garantisi verilmez.
- İstemci kapanınca akış biter; iki kontrol arasındaki beklemede DB bağlantısı havuza geri verilmiştir.

Canlı OpenAPI tanımı /openapi.json, deneme ekranı /docs adresindedir.

## Canlı metrik akışı

API sürümü 0.5.0. `GET /stream/metrics`, `text/event-stream` döndürür. `service`, `name`, `unit`, `tags`, `start`, `end` filtreleri GET /metrics ile aynı yardımcı fonksiyonu kullanır. `limit` 1–200, varsayılan 100'dür; izlenen görünüm offset=0'dır. Geçersiz filtre ve limit başlıklardan önce 422 döndürür.

`metrics_changed`, ilk bağlantıda ve filtreli son `limit + 1` kaydın timestamp/id özeti değiştiğinde gönderilir. JSON içindeki revision ile olayın id alanı aynı özettir. İstemci aynı filtreler ve limit ile GET /metrics?offset=0 çağırır. Fazladan satır has_more durumunu izler. CPU paneli service + name=cpu_usage + unit=percent + limit=100 kullanır. Böylece başka metrik veya birim kendi grafiğini yeniletmez. İzlenen pencereye girmeyen daha eski kayıtlar bildirim üretmez.

Log akışındaki retry:3000, yaklaşık 15 saniyelik keepalive, iki saniyelik DB kontrolü, stream_status/unavailable, DB kurtarmasında eşitleme ve yeniden bağlantıda ilk bildirim davranışları burada da geçerlidir. Yalnızca commit edilmiş satırlar görülür. Olaylar her ölçümün kalıcı tekrar oynatımı değildir; güncel görünümü yeniden okutacak bildirimlerdir. Kayıtları değiştiren bir UPDATE API'si bulunmadığı için değişiklik özeti kimlik/zaman üzerinden hesaplanır; içerik düzenleme eklenirse bu izleme de genişletilmelidir.

### Panelde kullanılan metrik adları

Panel CPU için `name=cpu_usage&unit=percent`, bellek yüzdesi için `name=memory_usage&unit=percent`, yanıt süresi için `name=response_time&unit=ms` kullanır. GET ve SSE aynı seçili ad/birimle filtrelenir. API bu üç adla sınırlı değildir. Panelde yüzdeler 0–100, yanıt süresi negatif olmayan sonlu bir değer olarak beklenir; birim dönüşümü veya farklı serileri birleştirme yapılmaz.

## Görev takibi

GET /tasks/{task_id}: UUID biçimindeki kimlik için state, completed, successful döndürür. Durumlar PENDING, STARTED, RETRY, SUCCESS, FAILURE olabilir. Sonuçlar 24 saat saklanır. PENDING kimliğin var olduğunu kanıtlamaz; bilinmeyen veya süresi dolan kimlik için de dönebilir. Geçersiz kimlik 422, Redis erişim sorunu 503 döndürür. FAILURE durumunda genel açıklama verilir; hata ayrıntısı ve traceback worker loglarında kalır.
