# 🤖 Universal Media Downloader Bot

**InstaAudioBot** — bu Telegram orqali YouTube, Instagram va YouTube Music platformalaridan video va audio yuklab olish uchun yaratilgan kuchli va zamonaviy bot. Loyiha yuqori tezlik va barqarorlikni ta'minlash uchun **Docker**, **Redis**, **Celery** va **yt-dlp** texnologiyalaridan foydalanadi.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-blueviolet.svg?logo=telegram)](https://docs.aiogram.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🔥 Asosiy Imkoniyatlar

### 📹 YouTube
- **Video Sifatini Tanlash**: 144p dan 4K gacha bo'lgan sifatlarda yuklash (Progressive va DASH formatlarni qo'llab-quvvatlaydi).
- **Tezkor Format Aniqlash**: Videoning mavjud formatlarini soniyalar ichida aniqlash.
- **Audio Ajratish**: Videolarni audio formatda (M4A/MP3) yuklab olish.
- **Katta Fayllar**: 2GB gacha bo'lgan fayllarni muammosiz yuborish.

### 📸 Instagram
- **Universal Yuklash**: Reels, Postlar (rasm va video), Stories va IGTV.
- **Carousel Qo'llab-quvvatlash**: Bir nechta rasm/videodan iborat postlarni to'liq yuklash.
- **Login Talab Qilinmaydi**: Ko'p hollarda akkauntga kirish shart emas.

### 🎵 YouTube Music & Shazam
- **Musiqa Qidiruv**: Nom yoki ijrochi bo'yicha qidirish.
- **To'liq Metadata**: Albom rasmi (cover), ijrochi va qo'shiq nomi bilan yuklash.
- **Shazam Integratsiyasi**: Ovozli xabar yoki videodan musiqa aniqlash (ShazamIO).

---

## 🚀 O'rnatish va Ishga Tushirish

Loyihani ishga tushirish uchun serveringizda **Docker** va **Docker Compose** o'rnatilgan bo'lishi kerak.

### 1. Loyihani yuklab olish

```bash
git clone https://github.com/username/downloader-bot.git
cd downloader-bot
```

### 2. Sozlamalar (.env)

`env.example` namunasidan `.env` faylini yarating:

```bash
cp .env.example .env
nano .env
```

Quyidagi o'zgaruvchilarni to'ldiring:

```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11  # @BotFather dan olingan token
ADMINS=12345678,87654321                             # Admin ID lari (vergul bilan)
DB_USER=postgres
DB_PASS=parol
DB_NAME=insta_bot_db
DB_HOST=postgres
REDIS_HOST=redis
```

### 3. Cookies (Youtube va Instagram uchun)

Youtube va Instagram cheklovlaridan qochish uchun `cookies.txt` faylidan foydalanish tavsiya etiladi:
1. Brauzeringizdan (Chrome/Firefox) YouTube yoki Instagramga kiring.
2. "Get cookies.txt LOCALLY" (yoki shunga o'xshash) kengaytma orqali cookie faylni yuklab oling.
3. Faylni loyiha papkasiga `cookies.txt` nomi bilan joylashtiring.

---

## 🐳 Docker Orqali Ishga Tushirish (Tavsiya etiladi)

Barcha xizmatlarni (Bot, Database, Redis) bitta buyruq bilan ishga tushiring:

```bash
docker-compose up -d --build
```

Loglarni kuzatish uchun:

```bash
docker-compose logs -f
```

Botni to'xtatish uchun:
```bash
docker-compose down
```

---

## 🛠 Texnologik Stack

- **Til**: Python 3.11
- **Framework**: Aiogram 3 (Asynchronous Telegram Bot API)
- **Database**: PostgreSQL + SQLAlchemy (Async)
- **Cache**: Redis (Foydalanuvchi holati va tezkor kesh uchun)
- **Media Engine**: 
  - `yt-dlp` (YouTube va umumiy platformalar uchun eng kuchli vosita)
  - `ffmpeg` (Video va audioni birlashtirish, format o'zgartirish uchun)
- **Infrastructure**: Docker & Docker Compose

---

## ❓ Ko'p So'raladigan Savollar (FAQ)

**Savol: Bot "Fayl juda katta" deyapti?**
Javob: Telegram bot API orqali 50MB, Local Bot API server orqali 2GB gacha fayl yuborish mumkin. Bu loyiha Local Server bilan ishlashga ham moslashgan (agar serveringizda sozlangan bo'lsa).

**Savol: YouTube tezligi past?**
Javob: YouTube ba'zi server IP larini cheklashi mumkin. `cookies.txt` ni yangilang yoki IPv6 ni o'chirib ko'ring (Docker network sozlamalarida).

**Savol: Instagram Stories yuklamayapti?**
Javob: Stories faqat login qilingan (cookies bor) holatda ishlaydi. `cookies.txt` faylingiz to'g'riligiga ishonch hosil qiling.

---

## 🤝 Hissa Qo'shish

Loyiha ochiq kodli (Open Source). Taklif va, xatoliklar bo'lsa **Issues** bo'limiga yozing yoki **Pull Request** yuboring.

---

## 📄 Litsenziya

MIT License. Isstalgan maqsadda foydalanishingiz mumkin.
