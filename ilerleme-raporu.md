# Observability Projesi İlerleme Raporu

**Tarih: 12 Ekim 2026**

## Mevcut durum

Faz 1 mimari araştırması, veri modeli ve API sözleşmesi hazırlandı. Faz 2 kapsamında veri toplama API'si, asenkron kayıt hattı ve anlık alarm motoru tamamlandı. Bağlantı havuzu, toplu veri alımı ve görev durum takibi eklendi. İşlevler gerçek API, Redis, Celery worker ve TimescaleDB ile doğrulandı; sınırlı yerel yük ölçümleri yapıldı.

Uygulama → FastAPI → Redis → Celery worker → PostgreSQL/TimescaleDB → Kural kontrolü → Sistem içi alarm

## Tamamlanan çalışmalar

- Tekli log ve metrik alımı; 1-100 kayıt içeren toplu JSON dizileri.
- Pydantic doğrulaması, saat dilimli zaman, sonlu sayılar ve CPU yüzdesi sınırı.
- Loglarda servis, seviye, kelime, etiket ve zaman; metriklerde servis, ad, birim, etiket ve zaman filtreleri.
- En fazla 200 kayıtla limit/offset sayfalama.
- Kullanıcı tanımlı alarm kuralı oluşturma, listeleme, düzenleme ve kapatma.
- Metrik eşiği, hareketli zaman penceresinde log sayısı ve kural/servis bazlı tekrar bekleme.
- Sistem içi bildirim listeleme ve görüldü işareti.
- Görev kimliğiyle yeniden teslimde çift kayıt/alarmı engelleme.
- Toplu paketin kayıtlarını, görev kimliğini ve alarmlarını tek transaction içinde onaylama veya geri alma.
- Geçici bağlantı, kilit ve havuz hatalarında en fazla beş görev tekrarı.
- Havuzdan bağlantı ödünç alma; API süreci başına üst sınır 8, worker alt süreci başına 2.
- GET /tasks/{task_id} ile PENDING, STARTED, RETRY, SUCCESS ve FAILURE takibi.
- Redis'te görev sonuçlarını 24 saat tutma; başarısız görevleri kimlikle worker loglarında inceleme.
- Bağlantı sorunlarında 503, geçersiz girişlerde 422.
- Otomatik şema değişiklikleri, root olmadan çalışan worker, kurulum/API belgeleri ve satır açıklama rehberi.

## Varsayılan alarm kuralları

| Kural | Tetikleme şartı | Tekrar bekleme |
|---|---|---|
| CPU | cpu_usage, percent, değer > 85 | Servis başına 300 saniye |
| ERROR yoğunluğu | Serviste son 300 saniyede ERROR sayısı > 50 | Servis başına 300 saniye |

Kurallar yeni kayıt işlenirken anlık kontrol edilir. Log penceresi API alım zamanı received_at ile hesaplanır. CPU kuralı yeni gelen tek ölçümü değerlendirir. Görüldü işareti sistemin normale döndüğü anlamına gelmez.

## İşlevsel testler

Gerçek servislerle **16 senaryonun tamamı geçti**. Test çalıştırıcısının toplam süresi **6,49 saniye**; bu süre yük ölçümü değildir.

Kontroller: kayıt/filtreleme, eşik sınırları, servis ve birim ayrımı, sayfalama, kural düzenleme, onaylama, bekleme süresi, zaman penceresi, eşzamanlı tekrar teslim, transaction geri alma, toplu görevde çoklu alarm, bütün paketin doğrulanması, görev kimliği ve bağlantı satır biçimi.

## Kesinti ve kurtarma kontrolleri

| Senaryo | Sonuç |
|---|---|
| Worker kapalıyken gönderim, sonra worker açılması | SUCCESS; bir kayıt, bir görev makbuzu |
| Veritabanı kesintisi, sonra bağlantının geri gelmesi | RETRY gözlendi, sonra SUCCESS; bir kayıt |
| Çalışan worker alt sürecinin kaybı | Yeniden teslim; SUCCESS ve bir kayıt |
| Kontrollü kalıcı görev hatası | FAILURE; veritabanında kayıt oluşmadı |
| Redis kapalıyken POST /metrics | 503; 2,05 saniye |
| Veritabanı kapalıyken GET /metrics | 503; 5,02 saniye |

Servisler yeniden açıldı; /ready 200 döndü. Test verileri temizlendi, önceki örnek kayıtlar korundu.

## Yerel yük ölçümleri

Sekiz eşzamanlı gönderici kullanıldı. İlk üç satır yarı INFO log, yarı yüzde 70 CPU ölçümü içerir. Son satır yarı ERROR log, yarı yüzde 90 CPU ölçümü içerir.

| Sürüm ve gönderim | Kayıt | HTTP isteği | Tüm kayıtların yazılma süresi | Kayıt/saniye |
|---|---:|---:|---:|---:|
| Önceki sürüm, tekli | 1.000 | 1.000 | 7,301 sn | 136,98 |
| Yeni sürüm, tekli | 1.000 | 1.000 | 6,444 sn | 155,19 |
| Yeni sürüm, 100'lük paket | 1.000 | 10 | 0,309 sn | 3.238,71 |
| Alarm koşulları, 100'lük paket | 10.000 | 100 | 5,480 sn | 1.824,67 |

Tüm kayıtlar HTTP hatası olmadan kaydedildi. Son çalışmada iki beklenen alarm oluştu. Yeni tekli sürümde HTTP p95 63,13 ms, 100'lük paketlerde 138,80 ms olarak ölçüldü. HTTP süresi kuyruğa kabul cevabıdır; toplam süre bütün kayıtların veritabanında görülmesine kadar hesaplanır.

Bunlar tek bilgisayarda birer yerel denemedir. Sürekli yük kapasitesi veya üretim performansı garantisi değildir. Yeni sürümde havuzun yanında görev durum takibi de değiştiğinden fark yalnızca havuza bağlanamaz.

Sonuçlar: test-results/backend-checks.json, recovery-checks.json, outage-checks.json ve load-*.json.

## Kalan proje işleri

Faz 3 React paneli ve SSE canlı akışı; Faz 4 sürekli rastgele veri simülatörü, kapsamlı yük testleri, erişim denetimleri, canlıya alma ve sunum.

PENDING bilinmeyen veya süresi dolmuş görev kimliğini de temsil edebilir. API'ye yeniden POST gönderilmesi yeni görev oluşturur; istemci tekrarlarını engelleyecek idempotency anahtarı henüz uygulanmamıştır. Bunlar kurulum ve API belgelerinde açıklanmıştır.


## 18 Ekim 2026 Faz 3 başlangıcı

React ve Vite ile frontend klasörü oluşturuldu. İlk ekran API, veritabanı ve Redis bağlantısını kontrol edecek servis kartlarını içerir. Düğme GET /api/ready çağrısı yapar; Vite geliştirme proxy'si isteği mevcut FastAPI /ready ucuna iletir. Backend kodu değiştirilmedi. İlk sürümde grafik, log listesi ve SSE bulunmuyor.

React 19.3.1, Vite 8.3.4 ve ilgili paketler kuruldu; sürümler package.json ve package-lock.json içinde sabitlendi. npm run build başarılı oldu; geliştirme sunucusu 127.0.0.1:5173 üzerinde başlatıldı ve kontrol sonunda kapatıldı. Tarayıcı erişim izni reddedildiğinden görsel ve tıklama doğrulaması yapılamadı. FastAPI 8000 portunda yanıt vermediğinden gerçek servislerle panel bağlantısının uçtan uca doğrulaması sonraki adımda yapılacak. Önceki backend test sonuçları 12 Ekim'e aittir; yeniden çalıştırılmadı.

README'ye paneli çalıştırma adımları, .gitignore'a üretilen frontend dosyaları eklendi. Docker build bağlamında frontend klasörü dışlandı.


### 18 Ekim 2026 bağlantı düzeltmesi ve log tablosu

FastAPI başlatıldı. Hem /ready hem panel üzerinden /api/ready 200 dönüyor; veritabanı ve Redis erişimi doğrulandı. Bağlantı kontrolünde API hatası artık kartlarda gösteriliyor; son kontrol saati eklendi.

React LogTable bileşeni eklendi. Tablo olay zamanına göre son 20 kaydı yükler; zaman, servis, seviye ve mesaj alanlarını gösterir. Yenileme düğmesi, yüklenme, boş sonuç ve hata durumları hazırlandı. İstekler 15 saniyeyle sınırlandırıldı; bileşen kaldırılırsa istek iptal edilir. Henüz SSE, filtreleme, sayfalama veya hata detay ekranı eklenmedi.

GET /logs?limit=20 ve panel üzerinden GET /api/logs?limit=20 yanıtlarında iki mevcut kayıt ve beklenen alanlar doğrulandı. React derlemesi başarılı oldu. Yeni test kaydı oluşturulmadı. Tarayıcıda otomatik görsel/tıklama kontrolü yapılmadı; önceki tarayıcı erişim izni reddi geçerlidir.


### 18 Ekim 2026 SSE canlı log güncellemesi

API sürümü 0.4.0 oldu. GET /stream/logs ile text/event-stream bağlantısı eklendi. Backend her açık SSE bağlantısı için son 20 logun zaman/kimlik listesini iki saniyede bir kontrol eder. Değişiklikte logs_changed bildirimi gönderir; React EventSource bunu alınca GET /logs ile tabloyu yeniden okur. Normal koşullarda güncelleme, worker transaction'ının commit edilmesinden sonraki yaklaşık iki saniyelik kontrol aralığında fark edilir. Kuyruk ve istek süreleri ayrıca etkiler.

İlk bağlantıda ve yeniden bağlantıda güncel listeyle eşitleme yapılır; geçmiş olaylar tekrar oynatılmaz. Kalp atışı, yeniden bağlanma süresi, akış açıkken veritabanı hatası ve geri gelince eşitleme eklendi. Panel canlı akış durumunu gösterir; arka plan yenilemesinde mevcut tablo yükleniyor ekranıyla değiştirilmez.

Yeni beş SSE testiyle toplam 21 test başarılı oldu. Çalıştırıcının kaydettiği toplam süre 11.85 saniyedir. SSE başlıkları ve ilk bildirim, commit edilmemiş kaydın görünmemesi, yeniden bağlantıda eşitleme ve gerçek API/kuyruk/worker sonrası bildirim gerçek servislerle kontrol edildi. DB hatasından toparlanma ve istemci kopunca sorguyu durdurma kontrollerinde test taklitleri kullanıldı. Panelin Vite yönlendirmesi üzerinden SSE ilk bildirimi ayrıca alındı. Test verileri temizlendi; tarayıcıdaki görsel/tıklama doğrulaması otomatik yapılmadı.

API ve React log akışı yerel geliştirme kapsamında hazırdır. Metrik grafikleri, log filtreleri/sayfalama ve hata detayları, alarm yönetim ekranı, kapsamlı kapasite testleri ve canlı dağıtım kalmaktadır. Çok sayıda SSE istemcisi için ortak değişiklik izleme/bildirim dağıtımı henüz uygulanmamıştır.


### 18 Ekim 2026 log filtreleri ve sayfalama

API 0.4.1 ile log listesinin filtre oluşturması ortak log_filters fonksiyonuna alındı. SSE aynı servis, seviye, kelime, etiket ve zaman filtrelerini kullanır. Kontrol penceresi, 20 kayıtlık sayfanın yanında has_more bilgisini güncellemek için 21. kaydı da izler.

Panelde servis, seviye, kelime ve başlangıç/bitiş zamanı formu; Uygula ve Temizle; 20 kayıtlık sayfalama eklendi. Tarihler tarayıcının yerel saatinden UTC'ye dönüştürülür. Geçersiz zaman aralığı gönderilmez. Yazılan filtreler ancak Uygula ile devreye girer. Filtre değişince ilk sayfaya dönülür; eski sorgunun yanıtı yeni görünümde gösterilmez. İlk sayfa dışındayken SSE kapatılır; ilk sayfaya dönünce yeniden açılır. Offset sayfaları anlık görüntü garantisi taşımaz; arada eklenen kayıtlar sıralamayı değiştirebilir.

Açık SSE bağlantısının geliştirme sunucusunun yeniden başlatılmasını bekletmesi giderildi: Uvicorn komutuna 3 saniyelik graceful shutdown sınırı eklendi. İlk test çalışması bu bekleme yüzünden tamamlanamadı; sunucu yeniden başlatıldı, kesilen denemenin 20 kaydı temizlendi ve kontroller tekrar çalıştırıldı.

Güncel sonuç: 24 backend/SSE testi başarılı; çalıştırıcının toplam süresi 18.16 saniye. Yeni kontroller, genel son 21 kaydın dışında kalan filtreli kayıt için canlı bildirimi, eşleşmeyen kayıtların bildirime yol açmamasını, 20'den 21 kayda geçerken sonraki sayfa bayrağının güncellenmesini ve akış başlamadan filtre doğrulamasını kapsar. Dört Node testi URL özel karakterlerini, yerel saat/UTC dönüşümünü, ters aralıkları ve sayfa sınırlarını doğruladı. Vite üzerinden aynı servis/seviye/zaman filtreleriyle GET ve SSE yanıtları da alındı. Derleme başarılı; tarayıcıda otomatik görsel/tıklama testi yapılmadı. Test kayıtları temizlendi, üç mevcut örnek/gerçek log korundu.

Sıradaki geliştirme hata detaylarının görüntülenmesidir. Metrik grafikleri ve alarm yönetim ekranı henüz tamamlanmamıştır.


### 18 Ekim 2026 log detay penceresi

Log tablosuna Detay düğmesi ve ayrı LogDetails bileşeni eklendi. Pencere mevcut API yanıtındaki tam mesaj, servis, seviye, timestamp, received_at, tags ve stack_trace alanlarını kullanır. Yeni backend ucu veya veritabanı değişikliği yapılmadı. Tablodaki uzun mesajlar üç satırla önizlenir; detayda tam metin yer alır. Hata izi veya etiket yoksa eksik bilgi durumu açıkça gösterilir.

Tarayıcının native dialog/showModal mekanizması kullanıldı. Kapat düğmesi veya Escape ile kapanma; arka sayfanın etkileşiminin engellenmesi; sayfa kaydırmasının geçici kilitlenmesi ve kapanınca odağın açan düğmeye dönmesi eklendi. Canlı akış nedeniyle düğme artık listede değilse odak tablo başlığına döner. İncelenen kayıt, liste yenilendiğinde başka kayıtla değiştirilmez.

Derleme başarılı oldu. Bileşenin sunucu tarafında HTML üretimiyle uzun mesajın sonunun korunması, çok satırlı hata izi, iç içe JSON etiketleri ve boş ek alan açıklamaları kontrol edildi. Metin içindeki HTML işaretlerinin metin olarak çıktığı doğrulandı. Panelin /api yönlendirmesinden mevcut üç kaydın gerekli detay alanlarını taşıdığı doğrulandı. Yeni test kaydı oluşturulmadı ve backend testleri bu UI değişikliği için yeniden çalıştırılmadı. Tarayıcıda otomatik açma/kapatma, klavye ve görsel kontrol yapılmadı; kullanıcıyla kontrol edilecek.

Faz 3'te sonraki geliştirme canlı metrik grafikleri; ardından alarm yönetim ekranıdır.
