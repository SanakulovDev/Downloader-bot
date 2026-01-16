from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Video Yuklash"), KeyboardButton(text="🎵 Musiqa Qidirish")]
    ],
    resize_keyboard=True
)
