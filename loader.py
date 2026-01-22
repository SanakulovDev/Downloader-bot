from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
import os
from core.config import get_settings
import logging

settings = get_settings()
BOT_TOKEN = settings.bot_token
REDIS_HOST = settings.redis_host
REDIS_PORT = settings.redis_port
TMP_DIR = settings.tmp_dir

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Setup
from aiogram.client.telegram import TelegramAPIServer

if settings.use_local_server:
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(settings.local_server_url),
        timeout=1800
    )
else:
    session = AiohttpSession(timeout=1800)

bot = Bot(token=BOT_TOKEN, session=session)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Redis will be initialized in app.py or a separate db module, 
# but we can keep a reference here if needed, or better yet, attached to dp.
# For now, let's keep it simple global
redis_client = None

# Database
from utils.db_api.database import async_session
db = async_session
