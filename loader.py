from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
import os
from dotenv import load_dotenv
import logging

load_dotenv('app/.env')

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
TMP_DIR = os.getenv('TMP_DIR', '/dev/shm/tmp')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Setup
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
