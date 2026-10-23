# Yerel yük testi raporu — 24 Ekim 2026

## Amaç ve yöntem

Veri kabulü, kuyrukta işlenme ve kalıcı kayıt hattı ölçüldü:

`Yük üreticisi → FastAPI → Redis → Celery worker → TimescaleDB / alarm`

Her deneme farklı bir `qa-load-...` servis adı kullandı. Başarı için HTTP kabulü, log/metrik sayıları, görev makbuzlarının sayısı/içerdiği kayıt sayısı ve tüm Celery görevlerinin SUCCESS durumu birlikte kontrol edildi. Test verileri bu doğrulamalardan sonra temizlendi. Raporlar korundu.

Ortam: Windows 11, istemcide Python 3.14.3; API 127.0.0.1:8000 üzerinde tek Uvicorn süreciyle, reload ve erişim günlüğü kapalı çalıştı. Docker/WSL üzerinde Redis 7.4-alpine, TimescaleDB latest-pg17 ve iki eşzamanlı Celery işçisi kullanıldı. Yerel sistem 24 mantıksal işlemci bildiriyor; bu sayı konteynere ayrılmış çekirdek garantisi değildir. Paket üreticisi API/worker/DB ile aynı bilgisayarda çalıştı. React paneli/çoklu SSE izleyicileri bu yük profillerine dahil edilmedi.

## Sonuç özeti

İlk iki satırda üç tekrarın **ortanca değerleri** yer alır. Diğer profiller birer kez çalıştırıldı. p95 sütunu ilk iki satır için her denemenin p95 değerinin ortancasıdır; tüm istekleri birleştirerek hesaplanmış p95 değildir.

| Profil | Kayıt / tekrar | Paket | HTTP isteği / tekrar | DB doğrulama süresi | Kayıt/sn | HTTP p95 | HTTP hatası |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tekli normal, 3 tekrar | 1.000 | 1 | 1.000 | 2,623 sn | 381,31 | 29,12 ms | 0 |
| Paketli normal, 3 tekrar | 1.000 | 100 | 10 | 0,296 sn | 3.375,86 | 63,79 ms | 0 |
| Daha büyük normal yük | 10.000 | 100 | 100 | 1,832 sn | 5.458,83 | 78,06 ms | 0 |
| Alarm koşulları | 10.000 | 100 | 100 | 4,911 sn | 2.036,12 | 58,77 ms | 0 |
| 200 kayıt/sn hedefli gönderim | 12.000 | 100 | 120 | 59,749 sn | 200,84 | 46,75 ms | 0 |

Normal yük yarı INFO log ve yarı cpu_usage/percent=70 metriğidir. Alarm profilinde ERROR ve CPU %90 kullanıldı. İlgili çalışmada iki alarm üretildi; yeni bir denemede alarm sayısı o andaki etkin kurallara bağlıdır. Kural ayarları bu ölçümler için değiştirilmedi.

100 kayıtlık ön doğrulama dahil **10 denemede toplam 38.100 kayıt ve 3.360 HTTP isteği** işlendi. Kabul edilen ve DB'de bulunan kayıt sayıları eşleşti, bütün görevler SUCCESS oldu. HTTP hata sayısı sıfırdı. Ön doğrulama, tekli/paket karşılaştırmasının istatistiğine dahil edilmedi.

## Tekrarların ayrıntıları

| Deneme | DB doğrulama | Worker onayı | HTTP p95 | HTTP p99 | Örneklenen en fazla bekleyen görev |
| --- | ---: | ---: | ---: | ---: | ---: |
| single-r1 | 2,623 sn | 3,377 sn | 29,04 ms | 39,17 ms | 422 |
| single-r2 | 2,655 sn | 3,538 sn | 29,97 ms | 36,03 ms | 395 |
| single-r3 | 2,371 sn | 3,248 sn | 29,12 ms | 32,72 ms | 393 |
| batch-r1 | 0,296 sn | 0,335 sn | 63,79 ms | 63,79 ms | 0 |
| batch-r2 | 0,296 sn | 0,369 sn | 27,27 ms | 27,27 ms | 0 |
| batch-r3 | 0,305 sn | 0,346 sn | 74,21 ms | 74,21 ms | 0 |
| bulk | 1,832 sn | 1,942 sn | 78,06 ms | 87,15 ms | 73 |
| alerting | 4,911 sn | 4,989 sn | 58,77 ms | 72,00 ms | 88 |
| paced | 59,749 sn | 59,823 sn | 46,75 ms | 91,98 ms | 0 |

Paket profilinde yalnızca 10 HTTP yanıtı olduğundan p95 ve p99 en büyük örneğe denk gelir; bu küçük örneklem, tek başına kararlı bir gecikme dağılımı göstermez.

## Sürekli gönderim denemesi

12.000 kayıt 100'lük paketlerle, 200 kayıt/saniye hedefiyle gönderildi. Bu ayarda yaklaşık yarım saniyede bir paket planlanır. Son kabul yanıtı başlangıçtan 59,520 saniye sonra geldi; tüm kayıtlar 59,749 saniyede DB'de doğrulandı. Gönderim sonrası ek DB beklemesi 0,229 saniye, tüm worker sonuçlarının onayı 59,823 saniyeydi. Başarılı kabul yanıtlarının p99 değeri 91,98 ms oldu.

İlk paket sıfırıncı saniyede gönderildiği için gönderim yaklaşık 59,5 saniyede tamamlanır; ölçülen 200,84 kayıt/sn değeri bundan ve kontrol zamanından etkilenir. Bu deneme yaklaşık bir dakikalık hedefli yükü doğrular; azami kapasite araması değildir.

## Ölçümleri nasıl yorumlamalıyız?

- **HTTP gecikmesi**, API'nin kuyruğa kabul yanıtına kadardır. Paketin DB'ye yazılma süresi değildir; tabloda istek başına verilmiştir.
- **DB doğrulama süresi**, ilk gönderimden tüm kayıt ve makbuzların görünmesine kadardır. SQL kontrolü gönderim bittikten sonra yapıldığı için gerçek son yazma anı için üst sınırdır. Yaklaşık 0,2 saniyelik sorgulama beklemesi ve SQL süresi de sonuca eklenebilir.
- **Worker onayı**, DB doğrulamasından sonra Redis'teki görev sonuçlarının okunmasını da içerir. Bu fark doğrudan worker'ın son işi ne zaman bitirdiğini ölçmez.
- **Kuyruk tepesi**, tüm yerel celery kuyruğunda 0,5 saniyede bir sayılan bekleyen görevlerin en yükseğidir; kayıt veya çalışan görev sayısı değildir. Kısa sıçramalar kaçabilir. 0 örneği hiç kuyruk oluşmadığını göstermez.
- Aynı 1.000 kayıt için paketli gönderim bu ortamda daha kısa sürdü. Tekli yöntem 1.000, paketli yöntem 10 görev oluşturdu; istek ve işlem sayısının azalması sonuçla uyumludur. Denemeler sistemin başka koşullarda aynı oranı koruyacağını kanıtlamaz.
- Normal ve alarm profilinde farklı veri koşulları kullanıldı; bu birer koşu yalnızca gözlenen farkı gösterir. 12 Ekim ölçümleri farklı ortam/ölçüm aracıyla yapıldığı için bu sonuçlarla doğrudan sürüm hızlanması oranı hesaplanmadı.
- Üretim kapasitesi, uzun süreli bellek/disk davranışı, çok kullanıcılı SSE panel yükü ve internet gecikmesi bu çalışma kapsamında ölçülmedi. Bir dakikalık sonuç saatlerce dayanıklılık veya azami hız garantisi değildir.

## Son kontrol ve temizlik

10 çalışmanın tamamında successful ve data_cleaned alanları true oldu. Ayrı son kontrolde bu servislerin logs, metrics, alerts ve alert_states tablolarında kalan satır sayıları sıfır bulundu. Redis'te bekleyen görev sayısı sıfırdı; /ready yanıtı API, DB ve Redis'in hazır olduğunu, worker istatistiği iki işçinin çalıştığını doğruladı.

Kontrol anında payment-service için 1 log, 7 metrik, 2 alarm; demo-payment için 10 log, 30 metrik, 1 alarm bulunuyordu. Bunlar test sonrası gözlemdir; ayrı bir önce/sonra karşılaştırması yapılmış gibi yorumlanmamalıdır. Temizlik sorguları yalnızca benzersiz test servisleri ve ilgili görev kimlikleriyle sınırlandırıldı.

Altı yeni birim testi başarılıdır: nearest-rank yüzdelikleri, CLI sınırları/dosya adı, kayıt sayısına göre hız planı, concurrency sınırı/tüm sonuçları toplama, hata sonrası yeni gönderimi durdurma ve kullanıcı servislerini temizlemeyi reddetme. Önceki backend/frontend işlevsel test paketlerinin tamamı bu yük ölçümü adımında yeniden çalıştırılmadı.

## Kanıt dosyaları

- `load-phase4-20261024-smoke.json`
- `load-phase4-20261024-single-r1.json`, `single-r2.json`, `single-r3.json` (hepsi aynı load-phase4-20261024- önekini kullanır)
- `load-phase4-20261024-batch-r1.json`, `batch-r2.json`, `batch-r3.json` (aynı önek)
- `load-phase4-20261024-bulk.json`
- `load-phase4-20261024-alerting.json`
- `load-phase4-20261024-paced.json`
- `load-verification-20261024.json`

JSON zamanları UTC'dir. 23 Ekim 23:xx UTC, Türkiye'de 24 Ekim 02:xx saatine karşılık gelir; rapor tarihi yerel tarihtir.
