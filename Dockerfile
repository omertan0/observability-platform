# Python içeren hazır Linux ortamı
FROM python:3.13-slim

# Konteyner içindeki çalışma klasörü
WORKDIR /app

# Paket listesini kopyala
COPY requirements.txt .

# Listedeki paketleri kur
RUN pip install --no-cache-dir -r requirements.txt

# Python dosyalarını kopyala
COPY main.py models.py celery_app.py tasks.py database.py alerts.py queries.py streams.py security.py host_agent.py request_telemetry.py ./

# Worker yönetici yetkisi olmadan çalışır.
RUN useradd --uid 10001 --create-home appuser
USER appuser

# Varsayılan komut worker'dır; Compose api servisi aynı dosyadan imaj
# oluşturur ve bu komutu Uvicorn ile değiştirir.
CMD ["celery", "-A", "tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
