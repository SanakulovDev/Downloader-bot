import asyncio
import os
import time
import logging
from loader import TMP_DIR

logger = logging.getLogger(__name__)

async def cleanup_worker():
    """Doimiy ravishda eski fayllarni tozalab turuvchi worker (24 soat)"""
    logger.info("♻️ Cleanup worker started")
    
    while True:
        try:
            # Har 5 daqiqada tekshiradi
            await asyncio.sleep(300)
            
            now = time.time()
            limit = 1800 # 30 daqiqa (sekundlarda)
            
            count = 0
            # TMP_DIR ichidagi fayllarni tekshirish
            if os.path.exists(TMP_DIR):
                for filename in os.listdir(TMP_DIR):
                    file_path = os.path.join(TMP_DIR, filename)
                    
                    # Faqat fayllarni tekshiramiz
                    if os.path.isfile(file_path):
                        # Faylni o'zgartirilgan vaqtini olish
                        file_mtime = os.path.getmtime(file_path)
                        
                        if now - file_mtime > limit:
                            try:
                                os.remove(file_path)
                                count += 1
                            except Exception as e:
                                logger.error(f"Failed to delete old file {filename}: {e}")
            
            if count > 0:
                logger.info(f"♻️ Cleanup: {count} old files deleted.")
                
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")
            await asyncio.sleep(60) # Xatolik bo'lsa 1 daqiqa kutib davom etadi
