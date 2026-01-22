from typing import Any

from services.redis_client import get_sync_redis

DEFAULT_LANG = "uz"
SUPPORTED_LANGS = {"uz", "ru"}

_TEXTS: dict[str, dict[str, str]] = {
    "choose_language": {
        "uz": "Xurmatli mijoz, \nO'zingizga mos tilni tanlang:",
        "ru": "Уважаемый клиент, \nВыберите удобный язык:",
    },
    "lang_uz": {
        "uz": "🇺🇿 O'zbekcha",
        "ru": "🇺🇿 Узбекский",
    },
    "lang_ru": {
        "uz": "🇷🇺 Русский",
        "ru": "🇷🇺 Русский",
    },
    "language_changed_uz": {
        "uz": "🇺🇿 Til o'zgartirildi: O'zbekcha",
        "ru": "🇷🇺 Язык изменен: Узбекский",
    },
    "language_changed_ru": {
        "uz": "🇷🇺 Til o'zgartirildi: Русский",
        "ru": "🇷🇺 Язык изменен: Русский",
    },
    "ask_name": {
        "uz": "👋 Assalomu alaykum! Botdan foydalanish uchun ismingizni kiriting:",
        "ru": "👋 Здравствуйте! Для использования бота введите ваше имя:",
    },
    "start_welcome": {
        "uz": (
            "👋 <b>Universal Media Botga xush kelibsiz!</b>\n\n"
            "Men quyidagilarni bajara olaman:\n"
            "📹 <b>Video yuklash:</b> Instagram yoki YouTube link yuboring.\n"
            "🎵 <b>Musiqa topish:</b> Qo'shiq yoki ijrochi nomini yozing.\n\n"
            "<i>Shunchaki link yoki nom yuboring, men o'zim tushunib olaman!</i> 🚀"
        ),
        "ru": (
            "👋 <b>Добро пожаловать в Universal Media Bot!</b>\n\n"
            "Я могу:\n"
            "📹 <b>Скачивать видео:</b> отправьте ссылку Instagram или YouTube.\n"
            "🎵 <b>Искать музыку:</b> напишите название песни или исполнителя.\n\n"
            "<i>Просто отправьте ссылку или название — я сам разберусь!</i> 🚀"
        ),
    },
    "registration_thanks": {
        "uz": (
            "Rahmat, {name}! Ro'yxatdan o'tdingiz.\n\n"
            "📹 <b>Video yuklash:</b> Instagram yoki YouTube link yuboring.\n"
            "🎵 <b>Musiqa topish:</b> Qo'shiq nomini yozing."
        ),
        "ru": (
            "Спасибо, {name}! Вы зарегистрированы.\n\n"
            "📹 <b>Скачивание видео:</b> отправьте ссылку Instagram или YouTube.\n"
            "🎵 <b>Поиск музыки:</b> напишите название песни."
        ),
    },
    "unsupported_url": {
        "uz": "❌ Hozircha faqat YouTube va Instagram linklari qo'llab-quvvatlanadi.",
        "ru": "❌ Сейчас поддерживаются только ссылки YouTube и Instagram.",
    },
    "video_loading": {
        "uz": "⏳ <b>Video yuklanmoqda...</b>",
        "ru": "⏳ <b>Видео загружается...</b>",
    },
    "music_loading": {
        "uz": "⏳ <b>Musiqangiz yuklanmoqda...</b>",
        "ru": "⏳ <b>Ваша музыка загружается...</b>",
    },
    "music_button_loading": {
        "uz": "⏳ Musiqa yuklanmoqda...",
        "ru": "⏳ Музыка загружается...",
    },
    "searching": {
        "uz": "🔍 Qidirilmoqda...",
        "ru": "🔍 Идёт поиск...",
    },
    "no_results": {
        "uz": "❌ Hech narsa topilmadi.",
        "ru": "❌ Ничего не найдено.",
    },
    "search_results": {
        "uz": "🎵 Natijalar (Sahifa {page}):",
        "ru": "🎵 Результаты (страница {page}):",
    },
    "search_tip": {
        "uz": "Musiqa qidirmoqchimisiz menga yozing va men bir zumda topib beraman.",
        "ru": "Хотите найти музыку? Напишите мне, и я быстро найду.",
    },
    "choose_format": {
        "uz": "Formatni tanlang:",
        "ru": "Выберите формат:",
    },
    "formats_header": {
        "uz": "📹 {title}\n👤 {uploader}\n\n{formats}\n\nFormatlar uchun ↓",
        "ru": "📹 {title}\n👤 {uploader}\n\n{formats}\n\nФорматы для скачивания ↓",
    },
    "format_line": {
        "uz": "🚀  {height}p: {size}",
        "ru": "🚀  {height}p: {size}",
    },
    "size_mb": {
        "uz": "{mb}MB",
        "ru": "{mb}MB",
    },
    "no_formats": {
        "uz": "❌ Formatlar topilmadi.",
        "ru": "❌ Форматы не найдены.",
    },
    "video_progress": {
        "uz": "⏳ <b>Video yuklanmoqda...</b> {percent}",
        "ru": "⏳ <b>Видео загружается...</b> {percent}",
    },
    "cancel": {
        "uz": "❌ Bekor qilish",
        "ru": "❌ Отмена",
    },
    "favorites_title": {
        "uz": "❤️ <b>Sizning sevimli musiqalaringiz:</b>",
        "ru": "❤️ <b>Ваши избранные треки:</b>",
    },
    "favorites_empty": {
        "uz": "🤷‍♂️ Sizda hali sevimli musiqalar yo'q.",
        "ru": "🤷‍♂️ У вас пока нет избранных треков.",
    },
    "favorites_cleared": {
        "uz": "🧹 Barcha musiqalar o'chirildi!",
        "ru": "🧹 Все треки удалены!",
    },
    "db_error": {
        "uz": "❌ Ma'lumotlar bazasi xatoligi",
        "ru": "❌ Ошибка базы данных",
    },
    "help_text": {
        "uz": (
            "📖 <b>Bot haqida ma'lumot:</b>\n\n"
            "1️⃣ <b>Video yuklash:</b> Link yuboring\n"
            "2️⃣ <b>Musiqa:</b> Qo'shiq nomini yozing (masalan: 'Believer')\n\n"
            "⚡ <b>Bot juda tez ishlaydi!</b>"
        ),
        "ru": (
            "📖 <b>О боте:</b>\n\n"
            "1️⃣ <b>Скачивание видео:</b> отправьте ссылку\n"
            "2️⃣ <b>Музыка:</b> напишите название песни (например: 'Believer')\n\n"
            "⚡ <b>Бот работает очень быстро!</b>"
        ),
    },
    "help_button": {
        "uz": "📝 Murojaat qoldirish",
        "ru": "📝 Оставить обращение",
    },
    "help_no_url": {
        "uz": "⚠️ Bot sozlanmagan (WEB_APP_URL yo'q).",
        "ru": "⚠️ Бот не настроен (нет WEB_APP_URL).",
    },
    "generic_error_retry": {
        "uz": "Xatolik yuz berdi, iltimos qaytadan urinib ko'ring /start",
        "ru": "Произошла ошибка, пожалуйста попробуйте снова /start",
    },
    "like_exists": {
        "uz": "⚠️ Bu musiqa sevimlilarda allaqachon bor!",
        "ru": "⚠️ Этот трек уже в избранном!",
    },
    "like_added": {
        "uz": "❤️ Sevimlilarga qo'shildi!",
        "ru": "❤️ Добавлено в избранное!",
    },
    "artist_not_found": {
        "uz": "❌ Muallif topilmadi",
        "ru": "❌ Исполнитель не найден",
    },
    "artist_searching": {
        "uz": "🎤 <b>{artist}</b> qo'shiqlari qidirilmoqda...",
        "ru": "🎤 <b>Идёт поиск песен {artist}</b>...",
    },
    "delete_failed": {
        "uz": "❌ O'chirib bo'lmadi",
        "ru": "❌ Не удалось удалить",
    },
    "delete_ok": {
        "uz": "✅ Xabar o'chirildi",
        "ru": "✅ Сообщение удалено",
    },
    "video_download_failed": {
        "uz": "❌ Video yuklab bo'lmadi.",
        "ru": "❌ Не удалось скачать видео.",
    },
    "music_download_failed": {
        "uz": "❌ Musiqa yuklashda xatolik bo'ldi.",
        "ru": "❌ Ошибка при загрузке музыки.",
    },
    "download_error_generic": {
        "uz": "❌ Yuklashda xatolik yuz berdi! (Keyinroq urinib ko'ring)",
        "ru": "❌ Произошла ошибка при загрузке! (Попробуйте позже)",
    },
    "send_error_generic": {
        "uz": "❌ Yuborishda xatolik yuz berdi!",
        "ru": "❌ Ошибка при отправке!",
    },
    "recognize_start": {
        "uz": "⏳ Musiqa aniqlanmoqda...",
        "ru": "⏳ Идет распознавание музыки...",
    },
    "audio_part_loading": {
        "uz": "🔍 Audio qismi yuklanmoqda... 0%",
        "ru": "🔍 Загружается аудиофрагмент... 0%",
    },
    "audio_loading_youtube": {
        "uz": "🔍 Audio yuklanmoqda... (Youtube)",
        "ru": "🔍 Аудио загружается... (YouTube)",
    },
    "audio_download_failed": {
        "uz": "❌ Audio yuklab bo'lmadi (Youtube blokladi).",
        "ru": "❌ Не удалось скачать аудио (YouTube заблокировал).",
    },
    "shazam_listening": {
        "uz": "🎧 Shazam orqali eshitilmoqda...",
        "ru": "🎧 Идет распознавание через Shazam...",
    },
    "shazam_not_found": {
        "uz": "❌ Afsuski, bu musiqani aniqlab bo'lmadi.",
        "ru": "❌ К сожалению, эту музыку распознать не удалось.",
    },
    "shazam_found": {
        "uz": "✅ Topildi: <b>{query}</b>\n\n🔍 Botdan qidirilmoqda...",
        "ru": "✅ Найдено: <b>{query}</b>\n\n🔍 Ищу в боте...",
    },
    "shazam_no_results": {
        "uz": "❌ '{query}' Shazamda topildi, lekin Youtubedan topa olmadim.",
        "ru": "❌ '{query}' найдено в Shazam, но на YouTube не нашел.",
    },
    "choose_variant": {
        "uz": "🎵 <b>'{query}'</b>\n\nQaysi birini yuklab beray?",
        "ru": "🎵 <b>'{query}'</b>\n\nКакой вариант скачать?",
    },
    "system_error": {
        "uz": "❌ Tizimda xatolik yuz berdi.",
        "ru": "❌ Произошла системная ошибка.",
    },
}

_ERROR_MAP: dict[str, dict[str, str]] = {
    "❌ Audio hajmi juda katta (2GB dan ortiq).": {
        "ru": "❌ Аудио слишком большое (более 2 ГБ).",
        "uz": "❌ Audio hajmi juda katta (2GB dan ortiq).",
    },
    "❌ Audio/Video topilmadi yoki o'chirilgan.": {
        "ru": "❌ Аудио/видео не найдено или удалено.",
        "uz": "❌ Audio/Video topilmadi yoki o'chirilgan.",
    },
    "❌ Yosh cheklovi yoki login talab qilinadi.": {
        "ru": "❌ Возрастное ограничение или требуется вход.",
        "uz": "❌ Yosh cheklovi yoki login talab qilinadi.",
    },
    "❌ Mualliflik huquqi tufayli yuklab bo'lmadi.": {
        "ru": "❌ Загрузка невозможна из-за авторских прав.",
        "uz": "❌ Mualliflik huquqi tufayli yuklab bo'lmadi.",
    },
    "❌ Hududiy cheklov tufayli yuklanmaydi.": {
        "ru": "❌ Недоступно из-за региональных ограничений.",
        "uz": "❌ Hududiy cheklov tufayli yuklanmaydi.",
    },
    "❌ Video hajmi juda katta (2GB dan ortiq). Telegram orqali yuborib bo'lmaydi.": {
        "ru": "❌ Видео слишком большое (более 2 ГБ). Нельзя отправить через Telegram.",
        "uz": "❌ Video hajmi juda katta (2GB dan ortiq). Telegram orqali yuborib bo'lmaydi.",
    },
    "❌ Video topilmadi yoki o'chirilgan (Private).": {
        "ru": "❌ Видео не найдено или удалено (Private).",
        "uz": "❌ Video topilmadi yoki o'chirilgan (Private).",
    },
    "❌ Bu video yosh cheklovi (18+) yoki login talab qiladi.": {
        "ru": "❌ Видео с возрастным ограничением (18+) или требуется вход.",
        "uz": "❌ Bu video yosh cheklovi (18+) yoki login talab qiladi.",
    },
    "❌ Bu video hududiy cheklov tufayli yuklanmaydi.": {
        "ru": "❌ Видео недоступно из-за региональных ограничений.",
        "uz": "❌ Bu video hududiy cheklov tufayli yuklanmaydi.",
    },
    "❌ Video yuklab bo'lmadi.": {
        "ru": "❌ Не удалось скачать видео.",
        "uz": "❌ Video yuklab bo'lmadi.",
    },
    "❌ Musiqa yuklashda xatolik bo'ldi.": {
        "ru": "❌ Ошибка при загрузке музыки.",
        "uz": "❌ Musiqa yuklashda xatolik bo'ldi.",
    },
    "❌ Yuklashda xatolik yuz berdi! (Keyinroq urinib ko'ring)": {
        "ru": "❌ Произошла ошибка при загрузке! (Попробуйте позже)",
        "uz": "❌ Yuklashda xatolik yuz berdi! (Keyinroq urinib ko'ring)",
    },
    "❌ Yuborishda xatolik yuz berdi!": {
        "ru": "❌ Ошибка при отправке!",
        "uz": "❌ Yuborishda xatolik yuz berdi!",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    text = _TEXTS.get(key, {}).get(lang)
    if not text:
        text = _TEXTS.get(key, {}).get(DEFAULT_LANG, key)
    return text.format(**kwargs)


async def get_user_lang(user_id: int, redis_client) -> str:
    if not redis_client:
        return DEFAULT_LANG
    try:
        lang = await redis_client.get(f"user:lang:{user_id}")
        if isinstance(lang, bytes):
            lang = lang.decode()
        if lang in SUPPORTED_LANGS:
            return lang
    except Exception:
        pass
    return DEFAULT_LANG


async def set_user_lang(user_id: int, lang: str, redis_client) -> None:
    if not redis_client:
        return
    if lang not in SUPPORTED_LANGS:
        return
    try:
        await redis_client.set(f"user:lang:{user_id}", lang)
    except Exception:
        pass


def get_user_lang_sync(user_id: int) -> str:
    client = get_sync_redis()
    if not client:
        return DEFAULT_LANG
    try:
        lang = client.get(f"user:lang:{user_id}")
        if isinstance(lang, bytes):
            lang = lang.decode()
        if lang in SUPPORTED_LANGS:
            return lang
    except Exception:
        pass
    return DEFAULT_LANG


def translate_error(text: str, lang: str) -> str:
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return _ERROR_MAP.get(text, {}).get(lang, text)
