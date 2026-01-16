#!/bin/bash

# Ngrok va Webhook setup script - Python bot uchun

echo "🔧 Telegram Bot Webhook Setup"
echo "=============================="
echo ""

# .env faylini tekshirish
if [ ! -f "./app/.env" ]; then
    echo "❌ .env fayl topilmadi! Avval .env.example dan .env yarating."
    exit 1
fi

# BOT_TOKEN ni o'qish
source ./app/.env
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN .env faylida topilmadi!"
    exit 1
fi

echo "📦 Ngrok o'rnatilganligini tekshiryapman..."
if ! command -v ngrok &> /dev/null; then
    echo "❌ Ngrok topilmadi!"
    echo "📥 Ngrok o'rnatish: https://ngrok.com/download"
    exit 1
fi

echo "✅ Ngrok topildi"
echo ""
echo "⚠️  Ngrok ni alohida terminalda ishga tushiring:"
echo "   ngrok http 8080"
echo ""
read -p "Ngrok ishga tushirildimi? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Ngrok ni ishga tushiring va keyin qayta urinib ko'ring."
    exit 1
fi

sleep 2

# Ngrok API dan public URL ni olamiz
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o 'https://[^"]*\.ngrok[^"]*' | head -1)

# Agar ngrok-free.app topilmasa, boshqa formatlarni ham tekshiramiz
if [ -z "$NGROK_URL" ]; then
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
fi

if [ -z "$NGROK_URL" ]; then
    echo "❌ Ngrok URL topilmadi! Ngrok ishlayotganini tekshiring."
    echo "💡 Ngrok ni ishga tushiring: ngrok http 8080"
    exit 1
fi

WEBHOOK_URL="${NGROK_URL}/webhook"
echo "✅ Ngrok URL: $NGROK_URL"
echo "🔗 Webhook URL: $WEBHOOK_URL"
echo ""

# .env faylga WEBHOOK_URL ni qo'shish
if ! grep -q "WEBHOOK_URL" ./app/.env; then
    echo "WEBHOOK_URL=${WEBHOOK_URL}" >> ./app/.env
    echo "✅ WEBHOOK_URL .env faylga qo'shildi"
fi

# Telegram webhook ni o'rnatish
echo "📤 Telegram webhook o'rnatilmoqda..."
RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✅ Webhook muvaffaqiyatli o'rnatildi!"
    echo ""
    echo "📋 Webhook ma'lumotlari:"
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""
    echo "💡 Ngrok ni to'xtatish uchun: pkill ngrok yoki Ctrl+C"
    echo ""
    echo "🚀 Endi webhook_server.py ni ishga tushiring:"
    echo "   python webhook_server.py"
else
    echo "❌ Webhook o'rnatishda xatolik!"
    echo "Javob: $RESPONSE"
    exit 1
fi

