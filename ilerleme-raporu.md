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


### 18 Ekim 2026 canlı CPU grafiği

Recharts 3.10.1 ile servis seçilebilen CPU yüzdesi grafiği eklendi. Seçilen servisin cpu_usage/percent türündeki son 100 kaydı olay zamanına göre çizilir. X ekseni gerçek geçen zamana, Y ekseni 0–100 yüzde aralığına dayanır. Kayıtlı son değer ve ölçüm zamanı gösterilir. Boş veri, tek nokta, istek hatası ve bağlantı toparlama durumları ayrıldı; grafik verisi tablo olarak da okunabilir. Grafik bilgisayardan CPU ölçmez; uygulamaların gönderdiği gerçek kayıtları kullanır. Servisin farklı host etiketleri ayrı serilere ayrılmaz; noktalar ayrı kayıtlardır. Grafik paketi ayrı JavaScript dosyasına bölündü.

API sürümü 0.5.0 oldu. GET /stream/metrics eklendi; liste ve SSE ortak metric_filters fonksiyonunu kullanır. metrics_changed bildirimi GET /metrics ile aynı filtreli görünümü yeniden okutur. Son limit+1 satır izlenerek daha eski kayıtların varlığı bilgisi de güncellenir. Log ve metrik akışlarında bağlantı, hata ve toparlanma döngüsü ortak revision_events fonksiyonuna alındı. Mevcut log davranışı korundu. Şema ve worker görevleri değiştirilmedi.

Doğrulama: 27 backend/SSE testi başarılı; çalıştırıcının kaydettiği toplam süre 26.65 saniye. Yeni üç test yanlış metrik/birimin bildirim üretmemesini, commit öncesi görünmemeyi, gerçek API/kuyruk/worker sonrası bildirimi, yeniden bağlantıda eşitlemeyi, 100 kayıt penceresi/has_more değişikliğini ve akış başlamadan doğrulamayı kapsar. Sekiz Node testi ve üretim derlemesi başarılıdır. Panelin Vite proxy'sinden GET /metrics ve SSE metrics_changed 200 yanıtları alındı; JSX dönüşümü 200 döndü. Bu kontroller tarayıcı görsel/tıklama testi değildir; tarayıcı otomasyonu yapılmadı.

Test kayıtları temizlendi; payment-service için önceki iki CPU ölçümü korundu. README, API sözleşmesi ve kod açıklamaları güncellendi. Word raporu bu adımda güncellenmedi. Faz 3 sürüyor; diğer metrik grafiklerinin genişletilmesi ve alarm yönetim ekranı kalıyor. Faz 4 simülatör, kapsamlı yük testleri, yayınlama ve teslim belgeleri ayrıca hazırlanacak.


### 18 Ekim 2026 grafik zaman görünümü düzeltmesi

Kullanıcının bildirdiği zamanların üst üste gelmesi incelendi. Gerçek veride 10–11 Ekim tarihli iki ölçümün yanında 18 Ekim 22:45, 22:46 ve 22:53 yerel saatli örnekler vardı. Bir haftalık tek eksende birkaç dakikalık yeni kayıtlar sağ kenara sıkışıyordu. 22:45 için iki ayrı değer de aynı olay zamanına sahipti; veri sıralamasında bozulma saptanmadı.

Grafiğe son kayıtlı ölçümden geriye 1 saat, 24 saat ve Tüm kayıtlar seçimi eklendi. Varsayılan bir saattir; mevcut son 100 kayda uygulanır. Gösterilen tarih sınırları ve kayıt sayısı yazılır. Eksen tarih/saat etiketleri iki satıra ayrıldı, kısa aralıkta saniye/milisaniye gösterimi ve dar ekranda daha az etiket eklendi. Aynı zamanlı kayıtlar korunur ve bilgi kutusunda birlikte listelenir; seçili aralığın tablosu da aynı kayıtları gösterir.

Kullanıcıdaki altı kaydın zaman dağılımını temsil eden test dahil üç yeni kontrol eklendi. Toplam 11 frontend testi ve derleme başarılı. Backend, şema ve kayıtlar değiştirilmedi; backend testleri bu frontend düzeltmesi için yeniden çalıştırılmadı. Tarayıcıda otomatik görsel veya tıklama doğrulaması yapılmadı.


### 18 Ekim 2026 CPU, bellek ve yanıt süresi seçimi

Metrik paneli CPU kullanımı, bellek kullanımı ve yanıt süresi arasında seçim yapacak şekilde genişletildi. Servis ve metrik formda seçilip Göster ile birlikte uygulanır. API sorguları ve SSE aynı servis/name/unit üçlüsüne geçer; eski istekler iptal edilir ve önceki serinin verisi yeni seçim altında gösterilmez. CPU cpu_usage/percent, bellek memory_usage/percent, yanıt süresi response_time/ms adlarını kullanır.

Yüzde grafikleri 0–100 aralığındadır; yanıt süresi 0'dan başlayan otomatik eksen kullanır. Özet, bilgi kutusu, tablo, başlık, erişilebilir açıklamalar ve boş sonuç mesajları seçilen türe göre değişir. 1 saat/24 saat/tüm kayıtlar görünümü ve aynı zamanlı kayıtların birlikte gösterimi korundu. Veri olmayan seride örnek değer üretilmez. Backend veya şema değişmedi.

Üç yeni frontend testi ile toplam 14 test ve üretim derlemesi başarılı. Geçici ve benzersiz servis altında response_time/ms=420.5 ile memory_usage/percent=64.2 kayıtları gerçek POST API, Redis, Celery worker, SSE ve Vite proxy üzerinden GET zinciriyle doğrulandı. Her seri yalnızca kendi kaydını döndürdü. Test kayıtları, görev sonuçları ve görev makbuzları temizlendi; kullanıcı kayıtları korunmuştur. 27 backend testinden oluşan önceki rapor bu frontend adımında yeniden çalıştırılmadı. Tarayıcıda otomatik görsel/tıklama doğrulaması yapılmadı.

README, API sözleşmesi ve kod açıklamaları güncellendi. Word raporu bu adımda değiştirilmedi. Faz 3'te sıradaki iş alarm yönetim ekranıdır. Faz 4 veri simülatörü/yük testleri, internette yayınlama ve teslim belgeleri devam edecektir.


### 18 Ekim 2026 alarm bildirim ekranı

React paneline Alarmlar bölümü eklendi. Alarm zamanı, servis, alarm oluştuğunda kaydedilmiş kural adı/açıklaması, inceleme durumu ve görülme zamanı listelenir. Varsayılan görünüm tüm servislerdeki incelenmemiş alarmlardır. Servis adı ve durum filtreleri Uygula ile gönderilir; 20 kayıtlık sayfalama ve manuel yenileme bulunur. İlk sayfa tamamlanan GET sonrasında yaklaşık 10 saniye arayla yenilenir; geçmiş sayfalarda otomatik yenileme durur. Bu bölüm SSE kullanmaz.

Görüldü düğmesi mevcut PATCH /alerts/{id}/acknowledge ucunu çağırır. Başarılı yanıt doğrulanır ve filtreli liste yeniden okunur. İşlem sürerken çakışan liste istekleri ve başka işlemler durdurulur. Filtre değişince önceki sorgu iptal edilir. Başarı/hata bildirimi, zaman aşımında sonucun belirsiz olabileceği açıklaması ve mesaj alanına klavye odağı eklendi. Görüldü, sorunun çözülmesi anlamına gelmez. Kullanıcının mevcut iki CPU alarmı test amacıyla işaretlenmedi.

Dört yeni frontend testi ile toplam 18 kontrol ve üretim derlemesi başarılıdır. Ayrı, benzersiz test servisi ve kuralıyla 21 alarm gerçek API/kuyruk/worker üzerinden oluşturuldu. Vite proxy üzerinden 20+1 sayfalama, servis/durum filtreleri, PATCH işlemi, tekrar işaretlemede ilk zamanın korunması ve işaretleme sonrası has_more bilgisinin güncellenmesi doğrulandı. Test kuralı, alarmlar, durumlar, metrikler, görev makbuzu ve Redis sonucu temizlendi. Backend kodu/şema değiştirilmedi; önceki 27 backend testi bu UI adımında yeniden çalıştırılmadı. Tarayıcıda otomatik görsel/tıklama kontrolü yapılmadı.

README ve kod açıklamaları güncellendi; Word raporu bu adımda değiştirilmedi. Faz 3'te alarm kuralı ekleme/düzenleme ve etkinleştirme ekranı kalmaktadır. Sonrasında Faz 4 simülatör, yük testleri, yayınlama ve teslim belgeleri hazırlanacaktır.


### 18 Ekim 2026 alarm kuralı yönetimi

React paneline Alarm kuralları ekranı eklendi. Mevcut kurallar koşul, servis kapsamı, tekrar bekleme ve etkinlik durumuyla listelenir; 20 kayıtlık sayfalama ve manuel yenileme bulunur. Yeni kural POST, düzenleme PATCH, açma/kapatma ise yalnızca enabled alanını içeren PATCH kullanır. Metrik eşiği ve log sayısı formları desteklenir. Metrik adı/birimi için öneriler yanında özel değerler de girilebilir. Servis boşsa tüm servisler ayrı değerlendirilir. Form, tür değişiminde kullanılmayan alanları null yapar; log karşılaştırmalarını gt/gte ile sınırlar. Boş sayı, sonlu olmayan sayı, pencere/bekleme sınırları ve tam sayı gereklilikleri kontrol edilir.

Kaydetme yanıtındaki kimlik ve alanlar doğrulanır. Başarıda liste yeniden alınır; hatada taslak korunur. İşlemler 15 saniyeyle sınırlandırılır, çift gönderim ve eski GET yanıtıyla durumun geri yazılması önlenir. Sonuç/form başlığı için klavye odağı eklendi. Tekrar beklemenin düzenleme/açma/kapatmada sıfırlandığı ve ayarların sonraki kayda uygulanacağı açıklanır. Eşzamanlı çok kullanıcılı düzenlemelerde sürüm çatışması denetimi yoktur. Backend ve şema değiştirilmedi.

Yedi yeni frontend testiyle toplam 25 kontrol ve üretim derlemesi başarılı. Entegrasyon verileri doğrudan üretimde kullanılan buildRulePayload fonksiyonundan oluşturuldu. Vite/API üzerinden yeni metrik ve log kuralları, eşik düzenleme, kapatma/açma, aynı isim için 409, logda geçersiz karşılaştırma için 422 ve log kuralından metrik kuralına dönüşüm kontrol edildi. Gerçek worker ile kapalı kuralın alarm üretmemesi, yeni eşiğin uygulanması, tekrar açılan kuralın üretmesi, log pencere/sayı koşulu ve eski alarm türünün korunması doğrulandı. Test kuralları, servis kayıtları, alarmlar, durumlar, görev makbuzları ve Redis sonuçları temizlendi. Kullanıcının mevcut kuralları değiştirilmedi. Önceki 27 backend testi bu UI adımında yeniden çalıştırılmadı. Tarayıcıda otomatik görsel/tıklama doğrulaması yapılmadı.

README ve kod açıklamaları güncellendi. Word raporu bu adımda değiştirilmedi. Faz 3 için planlanan yerel ekranların kodları eklendi; son tarayıcı görsel/etkileşim kontrolü bekliyor. Sonrasında Faz 4 sürekli simülatör, kapsamlı yük testleri, yayınlama ve son rapor/sunum/demo hazırlığı kalmaktadır.


### 18 Ekim 2026 Faz 4 veri simülatörü

scripts/simulate_telemetry.py eklendi. Standart Python kütüphanesiyle çalışan ayrı istemci, her servis/tur için bir log ve CPU/bellek/yanıt süresi olmak üzere üç metrik üretir. Güncel UTC zamanı kullanılır; kayıtlar simulation kaynağı, benzersiz run_id, sıra ve senaryo etiketleri taşır. Veri mevcut batch API üzerinden Redis/Celery/DB akışına girer; simülatör DB'ye doğrudan yazmaz ve kural ayarlarını değiştirmez.

Normal, hata ve karma senaryolar vardır. Karma senaryoda her beşinci tur yüksek CPU/bellek/yanıt süresi ve ERROR/hata izi gönderir. Varsayılan servis demo-payment, süre 60 saniye, tamamlanan turlar arası bekleme 2 saniyedir. Süre 0 verilirse Ctrl+C ile durdurulana kadar üretir. Turun iki Celery görevi SUCCESS olmadan sonraki tur başlamaz; kabul edilen ve onaylanan sayılar ayrılır. Worker hatası/süre aşımı üretimi durdurur. Belirsiz POST otomatik tekrarlanmaz. İsteğe bağlı JSON özetinde son 20 görev kimliği tutulur; bu uzun çalışmanın tam görev arşivi değildir.

Sekiz yeni simülatör testi başarılıdır. Testler API modellerine uygunluk, senaryolar/seed/güncel zaman, CLI sınırları, worker bekleme ve başarısızlık, süreli çalışma, belirsiz POST'u yeniden göndermeme ve Ctrl+C'yi kapsar. Gerçek API/kuyruk/worker/DB ve Vite üzerinden SSE/GET kontrolünde bir ERROR/hata izi ve üç metrik kaydedildi; ayrı test kurallarıyla CPU ve log alarmı oluştu. QA kayıtları, kurallar, durumlar, görev makbuzları ve Redis sonuçları temizlendi. Gerçek doğrulama özeti test-results/simulator-smoke.json içindedir.

Panel için 20 saniyelik karma demo ayrıca çalıştırıldı: 10 turda 10 log ve 30 metrik worker tarafından onaylandı. API'den geri okuma bu sayıları, iki ERROR kaydını ve bu çalışmadan bir CPU alarmını doğruladı. Demo servis kayıtları inceleme için bırakıldı; süreç süre sonunda kapandı. Özeti test-results/simulator-demo.json içindedir. Panelin alarm, kural ve üç metrik veri yanıtları gerçek frontend doğrulama yardımcılarıyla kontrol edildi. Tarayıcıda otomatik görsel/tıklama kontrolü yapılamadı; bu kontrol hâlâ bekliyor.

README ve kod açıklamaları güncellendi. Word raporu bu adımda değiştirilmedi. Önceki 25 frontend ve 27 backend/SSE testinin tamamı bu adımda yeniden çalıştırılmadı; bu adımın testi sekiz simülatör kontrolü ve gerçek servis denemeleridir. Simülatörün küçük demonun başarıyla tamamlanması kapasite kanıtı değildir. Bugünkü kapsam simülatöre kadar tamamlandı; kapsamlı yük testleri, yayınlama ve son teslim belgeleri/sunum/demo hazırlığı sonraki çalışmalardır.


### 18 Ekim 2026 Word raporu güncellemesi

Mevcut rapor.docx güncellendi. Araştırma ve 12 Ekim backend ölçümleri korundu; React paneli, canlı log/metrik akışı, alarm ve kural yönetimi, veri simülatörü, doğrulama sonuçları ve kalan işleri içeren 18 Ekim güncellemesi eklendi. Eski ilerleme bölümü tarihli geçmiş durum olarak açıklandı. 20 saniyelik demodaki 10 log, 30 metrik ve bir CPU alarmı rapora aktarıldı. Sekiz sayfanın düzeni görüntülenerek kontrol edildi. Rapor e-posta eki olarak paylaşılmaya hazırlandı; e-posta gönderilmedi.


### 24 Ekim 2026 — Faz 4 yerel yük testleri

Önce mevcut mimari ve tamamlanan ekranlar gözden geçirildi. Docker Desktop, DB, Redis ve iki işçili Celery worker başlatıldı; API tek Uvicorn süreciyle reload ve erişim günlüğü kapalı çalıştırıldı. Bu adımda backend'in veri kabulü, asenkron kayıt ve alarm hattı ölçüldü; React paneli veya çoklu SSE izleyicileri yük profiline dahil edilmedi.

scripts/load_backend.py geliştirildi. Gönderilecek kayıt ve eşzamanlı istek sayısı sınırlandı; kayıt/saniye hedefi, HTTP p99 ve yarım saniyelik kuyruk örnekleri eklendi. Görevler sınırlı sayıda HTTP isteğiyle gönderiliyor. HTTP hatası görüldüğünde yeni gönderim durduruluyor; sonucu belirsiz POST otomatik tekrarlanmıyor. Başarı artık yalnızca DB sayısına değil, log/metrik sayıları, görev makbuzlarının sayı/içerik toplamı ve tüm Celery SUCCESS sonuçlarına dayanıyor. Temizlik tamamlanan çalışmanın benzersiz test servisi ve görevleriyle sınırlandı; başarısız ölçümlerde veriler inceleme için korunuyor.

| Profil | Kayıt / tekrar | DB doğrulama süresi | HTTP p95 | Sonuç |
| --- | ---: | ---: | ---: | --- |
| Tekli gönderim, 3 tekrarın ortancası | 1.000 | 2,623 sn | 29,12 ms | Eksiksiz, HTTP hatası yok |
| 100'lük paket, 3 tekrarın ortancası | 1.000 | 0,296 sn | 63,79 ms | Eksiksiz, HTTP hatası yok |
| 100'lük paket, daha büyük normal yük | 10.000 | 1,832 sn | 78,06 ms | Eksiksiz, HTTP hatası yok |
| ERROR + CPU %90, 100'lük paket | 10.000 | 4,911 sn | 58,77 ms | Eksiksiz, iki alarm |
| 200 kayıt/sn hedefi, 100'lük paket | 12.000 | 59,749 sn | 46,75 ms | Eksiksiz, HTTP hatası yok |

100 kayıtlık ön deneme dahil toplam 10 koşuda 38.100 kayıt, 3.360 HTTP isteği işlendi; tamamı doğrulandı ve test verileri temizlendi. Son kontrolde bu servislerin log, metrik, alarm ve alarm durumlarında satır kalmadı; Redis kuyruğu boş, /ready hazır ve worker erişilebilirdi. Kullanıcıya ait payment-service ve demo-payment kayıtları DB'de bulunuyor. Son kontrolün ayrıntıları test-results/load-verification-20261024.json dosyasındadır.

Altı yeni yük üreticisi birim testi başarılı. Önceki frontend/backend işlevsel testlerinin tamamı bu adımda yeniden çalıştırılmadı. HTTP yüzdelikleri kuyruğa kabul cevabını ölçer; DB doğrulaması ayrı ölçümdür. DB sorguları gönderimden sonra başladığı için gerçek son yazma anı için üst sınır verir. Kuyruk örneklemesi kısa sıçramaları kaçırabilir. Bir dakikalık gönderim azami kapasite veya uzun süreli dayanıklılık garantisi değildir; 12 Ekim ölçümleriyle doğrudan sürüm hızlanması karşılaştırması yapılmadı.

README ve kod-aciklamalari.md güncellendi. Sayısal sonuçlar test-results/load-phase4-20261024-*.json içinde, yöntem ve yorum sınırları test-results/load-summary-20261024.md içindedir. Bu adımın raporu Markdown dosyalarına eklendi; Word belgesi için son güncelleme 18 Ekim bölümüdür.

Güncel durum: Faz 1 araştırma/tasarım ve Faz 2 veri hattı hazırlanmış durumda. Faz 3 ekran kodları tamamlandı; son tarayıcı görsel/etkileşim kontrolü bekliyor. Faz 4 simülatör ve yerel yük ölçümleri yapıldı. Sıradaki çalışma yayınlamaya hazırlık: kimlik doğrulama/erişim sınırları, dağıtım ayarları ve canlı ortam doğrulaması. Çok izleyicili/uzun süreli kapasite doğrulaması ile teslim raporu, sunum ve demo hazırlığı ayrıca kalmaktadır.
