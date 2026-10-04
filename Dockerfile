# Python içeren hazır Linux ortamı
FROM python:3.13-slim

# Konteyner içindeki çalışma klasörü
WORKDIR /app

# Paket listesini kopyala
COPY requirements.txt .

# Listedeki paketleri kur
RUN pip install --no-cache-dir -r requirements.txt

# Python dosyalarını kopyala
COPY main.py models.py celery_app.py tasks.py ./

# Konteyner açılınca worker'ı başlat
CMD ["celery", "-A", "tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]