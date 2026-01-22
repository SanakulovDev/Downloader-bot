from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from core.config import get_settings



from aiogram.client.telegram import TelegramAPIServer

def create_bot_session(timeout: int = 1800) -> tuple[Bot, AiohttpSession]:
    settings = get_settings()
    token = settings.bot_token
    
    if settings.use_local_server:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(settings.local_server_url),
            timeout=timeout
        )
    else:
        session = AiohttpSession(timeout=timeout)
        
    bot = Bot(token=token, session=session)
    return bot, session
