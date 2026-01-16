# ⚡ SuperFast Python Telegram Downloader Bot

**Eng tez va samarali** YouTube va Instagram video downloader bot.

## 🚀 Nima uchun Python?

✅ **Juda tez** - Async/await bilan parallel processing  
✅ **yt-dlp integratsiyasi** - Python library sifatida to'g'ridan-to'g'ri ishlatiladi  
✅ **aiogram** - Eng tez async Telegram bot framework  
✅ **Oson integratsiya** - Barcha tool'lar Python da  

## 📋 Talablar

- Python 3.11+
- Docker va Docker Compose
- Ngrok (webhook uchun)
- Telegram Bot Token

## 🔧 O'rnatish

### 1. Konfiguratsiya
```bash
cp app/.env.example app/.env
# app/.env faylini ochib, TELEGRAM_BOT_TOKEN ni kiriting
```

### 2. Docker orqali ishga tushirish (Tavsiya etiladi)

```bash
docker-compose up -d --build
```

### 3. Yoki lokal ishga tushirish

```bash
# Dependencies o'rnatish
pip install -r requirements.txt

# Bot ni ishga tushirish (polling)
python bot.py
```

### 4. Webhook orqali ishga tushirish (ngrok)

```bash
# Birinchi terminalda ngrok
ngrok http 8080

# Ikkinchi terminalda webhook setup
./setup-webhook.sh

# Uchinchi terminalda webhook server
python webhook_server.py
```

## 🎯 Ishlatish

Botga YouTube yoki Instagram video linkini yuboring:
- `https://www.youtube.com/watch?v=...`
- `https://www.instagram.com/reel/...`
- `https://www.instagram.com/p/...`

Bot video ni **juda tez** yuklab olib, sizga yuboradi!

## ⚡ Professional Level Optimizations

### 🔥 Instagram Direct JSON API (20x Tezroq)
- Instagram JSON API (`?__a=1&__d=dis`) orqali to'g'ridan-to'g'ri MP4 link
- 100% original sifat (no recompress)
- `instaloader` dan 20x tezroq

### 🔥 YouTube yt-dlp Optimizatsiyalari
- **Aria2c** - 16 parallel connections (juda tez!)
- **Throttling bypass** - YouTube tezlikni kamaytirishni chetlab o'tish
- **Silent download** - progress bar yo'q (tezroq)
- **Best format selection** - eng yuqori sifat

### 🔥 Redis Cache (10x Resurs Tejash)
- Bir URL bir marta yuklab olish, keyin cache dan berish
- 1 soat cache muddati
- 10x resurs tejash

### 🔥 Document Sifatida Yuborish (Lossless)
- Original file sifatida yuborish (Telegram qayta ishlamaydi)
- 2GB limit (50MB emas!)
- 100% original sifat

### 🔥 Docker Optimizatsiyalari
- `/dev/shm` mount (RAM-disk) - 2-5x tezroq
- **Ulimits** - ko'p fayl ochilganda bot yiqilmaydi
- **FFmpeg multi-thread** - multi-core CPU dan to'liq foydalanish

**Batafsil:** [OPTIMIZATIONS.md](OPTIMIZATIONS.md)

## 📊 PHP vs Python

| Xususiyat | PHP | Python |
|-----------|-----|--------|
| Tezlik | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| yt-dlp integratsiya | Subprocess | Native library |
| Async support | Limited | Full async/await |
| Memory usage | O'rtacha | Yaxshi |
| Development speed | O'rtacha | Tez |

## 🔍 Tuzatish

```bash
# Docker loglarini ko'rish
docker-compose logs -f

# Webhook ma'lumotlarini tekshirish
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

## 📝 Fayllar

- `bot.py` - Asosiy bot kodi (polling)
- `webhook_server.py` - Webhook server (ngrok uchun)
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker image
- `docker-compose.yml` - Docker Compose config
- `setup-webhook.sh` - Webhook setup script

