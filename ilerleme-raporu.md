# Observability Projesi İlerleme Raporu

**Tarih: 11 Ekim 2026**

## Mevcut durum

Log ve metriklerin API üzerinden alınması, Redis kuyruğuna gönderilmesi, Celery worker tarafından TimescaleDB tablolarına kaydedilmesi ve API üzerinden tekrar okunması tamamlandı. Kayıtları filtreleme ve kullanıcı tanımlı kurallarla sistem içi alarm oluşturma eklendi. Alarm aşamasında geliştirmeye ara verildi; sonraki çalışma mevcut kodun açıklanmasıdır.

`Uygulama → FastAPI → Redis → Celery worker → PostgreSQL/TimescaleDB → Kural kontrolü → Sistem içi alarm`

## Tamamlanan çalışmalar

- Logları servis, seviye, kelime, etiket ve zaman aralığıyla sorgulama.
- Metrikleri servis, ölçüm adı, birim, etiket ve zaman aralığıyla sorgulama.
- Sonuçlarda limit/offset ile sayfalama.
- Alarm kuralı oluşturma, listeleme, düzenleme ve devre dışı bırakma.
- Metrik eşiği ve hareketli pencerede log sayısı kuralları.
- Alarm listeleme ve görüldü olarak işaretleme.
- Tekrar bildirimler için kural/servis bazlı bekleme süresi.
- Görev tekrar teslim edilirse aynı görevin çift kayıt üretmesini engelleme.
- Kayıt, görev kimliği ve alarmı tek transaction içinde saklama.
- Geçici veritabanı/kilit hatalarında en fazla 5 görev tekrarı yapılandırması.
- Bağlantı sorunlarında açıklamalı 503; geçersiz girişlerde 422.
- Otomatik şema/alarm tablosu kurulumu ve root yetkisi olmadan çalışan worker.
- README, API sözleşmesi ve tekrar çalıştırılabilir işlevsel testler.

## Varsayılan alarm kuralları

| Kural | Tetikleme şartı | Tekrar bekleme |
|---|---|---|
| CPU | cpu_usage, percent, değer > 85 | Servis başına 300 saniye |
| ERROR yoğunluğu | Serviste son 300 saniyede ERROR sayısı > 50 | Servis başına 300 saniye |

Log penceresi API'nin aldığı zaman olan received_at ile hesaplanır. CPU kuralı yeni gelen ölçümü değerlendirir. Sistem içi bildirim seçeneği uygulanmıştır; e-posta/webhook gönderimi yoktur. Bildirimin görüldü olarak işaretlenmesi, ölçümün normale döndüğü anlamına gelmez.

## Test sonuçları

Gerçek API, Redis, Celery worker ve veritabanıyla **12 işlevsel senaryonun tamamı geçti**. Testler yaklaşık 4,94 saniyede tamamlandı; bu süre yük testi sonucu değildir.

| Kontrol | Sonuç |
|---|---|
| Log kaydetme ve servis/seviye/kelime/etiket/zaman filtreleri | Geçti |
| CPU tam 85 iken alarm olmaması, 85,1'de oluşması | Geçti |
| ERROR sayısı 50'de alarm olmaması, 51'de oluşması | Geçti |
| Tekrar bildirimlerin bekleme süresinde engellenmesi | Geçti |
| Servis ve metrik birimi ayrımı | Geçti |
| Kuralın kapatılması, düzenlenmesi ve doğrulanması | Geçti |
| Bildirimi tekrar onaylamanın zamanı değiştirmemesi | Geçti |
| Sayfalama ve uygunsuz girişlerin reddedilmesi | Geçti |
| Aynı görevin eşzamanlı tekrarında tek kayıt/alarm | Geçti |
| Alarm işleminde hata olursa tüm transaction'ın geri alınması | Geçti |
| Süresi geçen logların pencereden çıkarılması | Geçti |
| Bekleme süresi bitince yeni alarm ve kural adı çakışması | Geçti |

Ayrıca servisler kısa süre kapatılarak **2 bağlantı kesintisi senaryosu** kontrol edildi. Redis kapalıyken POST /metrics 503 cevabını 2,03 saniyede, veritabanı kapalıyken GET /metrics 503 cevabını 5,01 saniyede verdi. Her iki durumda /ready 503 döndürdü; servisler yeniden açıldığında 200 döndü. Bunlar tek yerel denemede gözlenen sürelerdir, performans garantisi değildir.

Makine tarafından kaydedilen sonuçlar: test-results/backend-checks.json ve test-results/outage-checks.json. Test verileri temizlendi; önceden oluşturulan örnek kayıtlar korundu.

## Kalan çalışmalar

React paneli ve SSE canlı akışı, simülatör/yük testleri, yüksek trafik iyileştirmeleri, kimlik doğrulama ve canlıya alma, teslim belgeleri ve sunum. Mevcut sürümün üretim ortamı hazırlığı ve yüksek trafik performansı henüz tamamlanmış sayılmaz. API'ye yeni POST göndermek yeni görev oluşturur; istemci tekrarları için ayrıca idempotency anahtarı gerekir. Başarısız son görevler worker loglarından izlenir.
