# 🤖 Universal Media Downloader Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-blueviolet.svg?logo=telegram)](https://docs.aiogram.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

**Universal Media Downloader** — bu Telegram orqali YouTube, Instagram va YouTube Music platformalaridan video va audio yuklab olish uchun yaratilgan yuqori tezlikdagi va zamonaviy bot. Loyiha eng so'nggi texnologiyalar (Asyncio, Redis, Celery) asosida qurilgan bo'lib, yuqori yuklamalarda ham barqaror ishlashga mo'ljallangan.

---

## 🔥 Asosiy Imkoniyatlar

### 📹 YouTube

- **Video yuklash**: Yuqori sifatli (1080p, 4K gacha) videolarni yuklash.
- **Audio ajratish**: Videodan faqat audio (MP3) trekni ajratib olish.
- **Playlistlar**: Butun playlistni bittada yuklash imkoniyati (kelajakda).
- **Tezlik**: `aria2c` multi-connection orqali maksimal tezlik.

### 📸 Instagram

- **Barcha turdagi kontent**: Reels, Posts, Stories va IGTV.
- **No-Login**: Instagram akkauntga kirish talab qilinmaydi (ba'zi hollarda).
- **Carousel**: Ko'p rasmli postlarni to'liq yuklash.

### 🎵 YouTube Music

- **Qidiruv**: Qo'shiq nomi yoki ijrochi bo'yicha qidirish.
- **Lyrics va Metadata**: Albom rasmi, ijrochi va qo'shiq nomi bilan to'liq fayl.
- **Yuqori Sifat**: 320kbps gacha audio sifati.

### 🚀 Texnik Ustunliklar

- **Redis Cache**: So'rovlarni keshlash orqali qayta yuklashlarni 10x kamaytirish.
- **Admin Panel**: Foydalanuvchilar statistikasi va bot boshqaruvi.
- **Background Tasks**: Celery va RabbitMQ yordamida og'ir vazifalarni fonda bajarish.
- **Dockerized**: To'liq Docker containerlarda ishlashga tayyor.

---

## 🛠 Texnologiyalar Stacki

- **Core**: Python 3.11, [Aiogram 3](https://docs.aiogram.dev/)
- **Downloaders**: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [Instaloader](https://instaloader.github.io/)
- **Music API**: [ytmusicapi](https://github.com/sigma67/ytmusicapi), [ShazamIO](https://github.com/shazamio/shazamio)
- **Database**: PostgreSQL (SQLAlchemy + AsyncPG)
- **Cache & Broker**: Redis, RabbitMQ
- **Task Queue**: Celery

---

## 🚀 O'rnatish va Ishga Tushirish

### Talablar

- Docker va Docker Compose
- Telegram Bot Token ([BotFather](https://t.me/BotFather))

### 1. Loyihani yuklab olish

```bash
git clone https://github.com/username/downloader-bot.git
cd downloader-bot
```

### 2. Konfiguratsiya

`app/.env.example` namunasidan nusxa olib, `.env` faylini yarating va sozlab chiqing:

```bash
cp app/.env.example app/.env
nano app/.env
```

**Muhim o'zgaruvchilar (.env):**

```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMINS=123456789,987654321
DB_USER=postgres
DB_PASS=postgres_pass
DB_NAME=downloader_db
DB_HOST=postgres
REDIS_HOST=redis
```

### 3. Docker orqali ishga tushirish (Tavsiya etiladi)

Loyihani to'liq (DB, Redis, Workerlar bilan) ishga tushirish uchun:

```bash
docker-compose up -d --build
```

Loglarni kuzatish:

```bash
docker-compose logs -f
```

---

## 🖥 Lokal Ishga Tushirish (Development)

Agar Docker ishlatmasdan, to'g'ridan-to'g'ri Python orqali ishlatmoqchi bo'lsangiz:

1. **Virtual muhit yaratish:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Kutubxonalarni o'rnatish:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Xizmatlarni ishga tushirish:**
   Sizga lokal Redis va PostgreSQL kerak bo'ladi. Ular ishga tushgach, `.env` faylida `localhost` deb ko'rsating.

4. **Botni ishga tushirish:**
   ```bash
   python bot.py
   ```

---

## 📁 Loyiha Tuzilishi

```
📂 downloader-bot
├── 📂 app/              # Konfiguratsiya fayllari
├── 📂 core/             # Asosiy sozlamalar (config, db)
├── 📂 downloads/        # Vaqtinchalik yuklangan fayllar
├── 📂 handlers/         # Telegram handlerlar (users, admins)
├── 📂 keyboards/        # Tugmalar (inline, reply)
├── 📂 services/         # Tashqi servislar (Youtube, Insta)
├── 📂 tasks/            # Celery vazifalari
├── 📂 utils/            # Yordamchi funksiyalar
├── 📄 bot.py            # Asosiy kirish nuqtasi
├── 📄 docker-compose.yml
└── 📄 requirements.txt
```

---

## ❓ Muammolar va Yechimlar

**Q: Bot video yuklamayapti?**
J: Serveringiz IP manzili YouTube yoki Instagram tomonidan bloklangan bo'lishi mumkin. Proxy ishlatishni ko'rib chiqing.

**Q: Dockerda xatolik: "No space left on device"?**
J: `docker system prune -a` buyrug'i orqali eski container va imagelarni tozalang.

---

## 🤝 Hissa Qo'shish (Contributing)

Loyihani rivojlantirishga hissa qo'shmoqchi bo'lsangiz, Pull Request yuborishingiz mumkin. Xatolik topgan bo'lsangiz, Issue oching.

## 📄 Litsenziya

Bu loyiha MIT litsenziyasi asosida tarqatiladi.
