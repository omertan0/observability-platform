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