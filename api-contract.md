# Veri Alım API Sözleşmesi

## Uç noktalar

- POST /logs: Tek bir log kaydı kabul eder.
- POST /metrics: Tek bir metrik kaydı kabul eder.

## Veri biçimi

İstek gövdesi JSON olmalıdır.
Content-Type: application/json kullanılmalıdır.

## Yanıtlar

- 202 Accepted: Veri doğrulandı ve işlenmek üzere kuyruğa alındı.
- 422 Unprocessable Entity: Gönderilen veri kurallara uymuyor.

## Ortak kabul kuralları

- timestamp zorunludur; saat dilimi içeren ISO 8601 biçiminde olmalıdır.
- service zorunludur; boş veya yalnızca boşluklardan oluşamaz.
- tags gönderilirse JSON nesnesi olmalıdır; gönderilmezse {} kullanılır.
- id veritabanı tarafından oluşturulur.
- received_at API tarafından, verinin alındığı anda belirlenir.

## Log kabul kuralları

- level zorunludur; INFO, WARN, ERROR veya FATAL olabilir.
- message zorunludur; boş veya yalnızca boşluklardan oluşamaz.
- stack_trace isteğe bağlıdır; metin veya null olabilir.

## Metrik kabul kuralları

- name ve unit zorunludur; boş veya yalnızca boşluklardan oluşamaz.
- value zorunludur; sonlu bir sayı olmalıdır.