
# 1. Base Image
FROM python:3.10-slim

# 2. Sistem performans ve log ayarları
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Çalışma dizini oluştur
WORKDIR /app

# 4. Gerekli sistem paketlerini kur (Postgres ve build araçları)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Bağımlılıkları kopyala ve kur
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 6. Proje dosyalarını kopyala
COPY . /app/

# 7. Static dosyaları topla (Collectstatic)
# Not: collectstatic sırasında DB bağlantısı gerekmemesi için dummy env variable kullanıyoruz
RUN DATABASE_URL="sqlite:///" python manage.py collectstatic --noinput

# 8. Portu aç
EXPOSE 8000

# 9. Başlatma komutu (Gunicorn)
# paygate.wsgi:application -> paygate projesinin wsgi dosyası
CMD ["gunicorn", "paygate.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
