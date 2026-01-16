import asyncio
from sqlalchemy import select, update
from utils.db_api.database import async_session
from utils.db_api.models import User, Broadcast
from loader import bot
import logging

logger = logging.getLogger(__name__)

async def broadcast_worker(broadcast_id: int):
    """
    Background task to send broadcast messages.
    """
    logger.info(f"Starting broadcast {broadcast_id}")
    
    async with async_session() as session:
        # Fetch broadcast details
        result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            logger.error(f"Broadcast {broadcast_id} not found")
            return

        # Fetch all users
        result = await session.execute(select(User.id))
        user_ids = result.scalars().all()
        
        # Update total count and status
        broadcast.total_users = len(user_ids)
        broadcast.status = "processing"
        await session.commit()
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                # Prepare media
                media = broadcast.file_id
                if media and (media.startswith("/app/") or media.startswith(".") or "/" in media):
                    from aiogram.types import FSInputFile
                    import os
                    if os.path.exists(media):
                        media = FSInputFile(media)
                
                if broadcast.message_type == 'text':
                    await bot.send_message(chat_id=user_id, text=broadcast.message_text)
                elif broadcast.message_type == 'photo':
                     await bot.send_photo(chat_id=user_id, photo=media, caption=broadcast.message_text)
                elif broadcast.message_type == 'video':
                     await bot.send_video(chat_id=user_id, video=media, caption=broadcast.message_text)
                elif broadcast.message_type == 'animation':
                     await bot.send_animation(chat_id=user_id, animation=media, caption=broadcast.message_text)
                
                sent += 1
            except Exception as e:
                # logger.error(f"Failed to send to {user_id}: {e}")
                failed += 1
            
            # Rate limit
            await asyncio.sleep(0.05)
            
            # Update stats periodically (e.g., every 10 users) or at end
            if (sent + failed) % 10 == 0:
                 # Re-fetch is problematic in long loop with same session usually, 
                 # simpler to use a separate update query or commit periodically.
                 # For safety/simplicity in this MVP, we create a new session or execute direct update
                 pass

        # Final update
        broadcast.sent_count = sent
        broadcast.failed_count = failed
        broadcast.status = "completed"
        await session.commit()
        logger.info(f"Broadcast {broadcast_id} finished. Sent: {sent}, Failed: {failed}")
