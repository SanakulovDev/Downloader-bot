# 🔧 Muammolarni Hal Qilish

## ❌ Bot Conflict Xatosi

**Xato:** `TelegramConflictError: terminated by other getUpdates request`

**Sabab:** Ikki bot instance bir vaqtda ishlayapti.

**Yechim:**
```bash
# 1. Docker container ni to'xtatish
docker-compose down

# 2. Barcha bot processlarni to'xtatish
pkill -f "python bot.py"

# 3. Qayta ishga tushirish
docker-compose up -d
```

**⚠️ Muhim:** Docker container ichida `python bot.py` ni ishga tushirmang! Container allaqachon bot ni ishga tushiradi.

## ❌ Video Yuklab Olishda Xatolik

**Muammo:** "❌ Yuklab olishda xatolik yuz berdi!"

**Yechimlar:**

1. **Video mavjudligini tekshiring**
   - Video public bo'lishi kerak
   - Video o'chirilmagan bo'lishi kerak

2. **Video hajmini tekshiring**
   - Telegram limit: 50MB
   - Katta videolar yuklab olinmaydi

3. **Internet aloqasini tekshiring**
   - Container internetga ulangan bo'lishi kerak

4. **Loglarni ko'ring**
   ```bash
   docker-compose logs -f
   ```

## 🔄 Container ni Qayta Ishga Tushirish

```bash
# Container ni restart qilish
docker-compose restart

# Yoki to'liq qayta build
docker-compose down
docker-compose up -d --build
```

## 📋 Foydali Komandalar

```bash
# Loglarni ko'rish
docker-compose logs -f

# Container ichiga kirish
docker exec -it python_downloader_bot bash

# Container holatini ko'rish
docker-compose ps

# Container ni to'xtatish
docker-compose stop

# Container ni o'chirish
docker-compose down
```

