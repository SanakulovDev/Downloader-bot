import asyncio
import logging
import redis.asyncio as redis
from aiogram import Dispatcher

from loader import bot, dp, REDIS_HOST, REDIS_PORT, redis_client
from utils.queue_handler import start_workers

# Import handlers
from handlers.users import start, video, music, echo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Bot ni ishga tushirish"""
    logger.info("🚀 Bot ishga tushmoqda...")
    
    # Redis ni ulash (cache uchun)
    # We need to set the global redis_client in loader module
    import loader
    try:
        loader.redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=False,
            socket_connect_timeout=2
        )
        await loader.redis_client.ping()
        logger.info("✅ Redis connected (cache enabled)")
    except Exception as e:
        logger.warning(f"Redis not available: {e} (cache disabled)")
        loader.redis_client = None

    # Start Workers
    workers = await start_workers()
    
    # Register Routers
    dp.include_router(start.router)
    dp.include_router(video.router)
    dp.include_router(music.router)
    dp.include_router(echo.router)

    # Webhook ni o'chirish (polling uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Polling ni boshlash
    try:
        await dp.start_polling(bot)
    finally:
        # Cancel workers on exit
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    
    # Redis ni yopish
    if loader.redis_client:
        await loader.redis_client.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi")
