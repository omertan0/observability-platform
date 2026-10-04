# FAZ 1 — Observability araştırması ve mimari tasarım

Bu belge, staj ödevinin ilk fazı için hazırlanıyor. Önce temel kavramları ve mevcut araçların mimarisini özetliyoruz. Veritabanı şeması ile API sözleşmesi sonraki adımlarda eklenecek.

## 1. Temel kavramlar

**Telemetry**, bir sistemin çalışırken ürettiği gözlem verilerinin genel adıdır. Üç temel türü vardır:

| Tür | Cevapladığı soru | Örnek |
| --- | --- | --- |
| Log | Ne oldu? | `odeme-api` bir ödeme isteğinde `ERROR` üretti. |
| Metrik | Ne kadar, ne sıklıkta? | CPU kullanımı saat 14:02'de `%87` oldu. |
| Trace | Bir istek hangi adımlardan geçti? | Ödeme isteği API, stok ve banka servislerinden geçti. |

Tek bir olayı bu üç veri türü farklı açılardan açıklar. Metrik hata oranındaki artışı gösterir; log belirli hatanın mesajını verir; trace o isteğin hangi serviste geciktiğini veya başarısız olduğunu gösterir. Bu projede log ve metrikler toplanıp görselleştirilecek; trace kavramı araştırma kapsamında ele alınacak.

## 2. APM ve izleme araçlarının mimarisi

**APM (Application Performance Monitoring)**, uygulamanın performansını ve hatalarını izlemek için kullanılan yaklaşım ve araçları ifade eder. İncelenen sistemlerde ortak akış, uygulamadan veri toplamak, veriyi işlemek/saklamak ve kullanıcıya sorgulanabilir bir ekranda sunmaktır.

### OpenTelemetry Collector

OpenTelemetry; log, metrik ve trace sinyallerini tanımlar. Collector, veriyi **receiver** ile alır, **processor** ile işleyebilir ve **exporter** ile bir depolama/analiz sistemine gönderir. Collector tek başına bu projenin dashboard veya veritabanı değildir; veri toplama hattına örnektir.

`Uygulama → Collector (al → işle → gönder) → Depolama/analiz sistemi`

### Elastic APM

Elastic'in örnek mimarisinde uygulamadaki agent/SDK veriyi toplar; APM alım servisi veriyi doğrular ve işler; Elasticsearch saklar; Kibana sorgulama ve görselleştirme sağlar. Buradan aldığımız temel fikir, **veri üreticisi**, **alım katmanı**, **depolama** ve **arayüz** sorumluluklarını ayırmaktır.

`Uygulama agent'ı → APM alım servisi → Elasticsearch → Kibana`

### Prometheus

Prometheus metriklere odaklanır. Genellikle uygulamaların sunduğu HTTP metrik adreslerini belirli aralıklarla **kendisi okuyarak** (pull/scrape) zaman serisi verisi toplar; kurallar üzerinden alarm üretir. Bizim ödevdeki ingestion API ise uygulamaların veriyi **gönderdiği** (push) bir giriş noktası olacak. Bu fark, mimari seçimimizdir; Prometheus'un çalışma şekliyle aynı olduğunu iddia etmiyoruz.

`Metrik adresleri → Prometheus toplama ve zaman serisi deposu → Sorgu/alarmlar/grafikler`

## 3. Projemiz için ilk mimari taslak

Yukarıdaki ortak katmanları ödevin gereksinimlerine uyguluyoruz:

`Örnek uygulama / simülatör → Ingestion API → Kuyruk → Worker → Zaman serisi deposu`

Depodaki kayıtlar okuma API'siyle sorgulanacak; yeni kayıtlar SSE ile canlı panele iletilecek. Alarm motoru kuralları değerlendirecek ve sistem içi bildirim oluşturacak. Bu, henüz uygulama değil; ilerleyen adımlarda netleştirilecek tasarımdır.

## 4. FAZ 1'de sıradaki işler

1. Yüksek hacimli kayıtlar için log ve metrik veritabanı şemasını tasarlamak.
2. Gönderilecek JSON biçimini ve ingestion API uç noktalarını belirlemek.
3. Bu tasarımı araştırma ve mimari raporunun son hâline getirmek.

## Kaynaklar

- [OpenTelemetry: Signals](https://opentelemetry.io/docs/concepts/signals/)
- [OpenTelemetry: Collector](https://opentelemetry.io/docs/collector/)
- [Elastic: APM Server](https://www.elastic.co/docs/solutions/observability/apm/apm-server/setup)
- [Prometheus: Overview](https://prometheus.io/docs/introduction/overview/)

Kaynaklar 2 Ekim 2026 tarihinde kontrol edildi.
