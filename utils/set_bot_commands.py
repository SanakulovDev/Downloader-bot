from aiogram import Bot
from aiogram.types import BotCommand

async def set_default_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="music", description="Musiqa qidirish"),
        BotCommand(command="video", description="Video yuklash"),
    ]
    await bot.set_my_commands(commands)
    
