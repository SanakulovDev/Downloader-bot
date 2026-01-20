FROM python:3.11-slim

COPY --from=denoland/deno:bin /deno /usr/bin/deno

# Sistem paketlarini o'rnatish
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/nodejs /usr/bin/node || true

# FFmpeg multi-thread enable
ENV OMP_NUM_THREADS=4

# Working directory
WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Bot kodini ko'chirish
COPY . .

# app/ papkasini yaratish (.env fayl docker-compose.yml orqali mount qilinadi)
RUN mkdir -p ./app

# TMP directory yaratish
RUN mkdir -p /dev/shm/tmp

# Bot ni ishga tushirish
CMD ["python", "app.py"]

