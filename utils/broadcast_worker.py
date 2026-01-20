from utils.db_api.models import User, Broadcast, BroadcastMessage
from loader import bot
import logging
import asyncio
from sqlalchemy import select
from utils.db_api.database import async_session

logger = logging.getLogger(__name__)

async def broadcast_worker(broadcast_id: int):
    """
    Background task to send broadcast messages.
    """
    logger.info(f"Starting broadcast {broadcast_id} (DEBUG TRACE)")
    print(f"DEBUG: Starting broadcast_worker for {broadcast_id}")
    
    try:
        async with async_session() as session:
            print("DEBUG: Session opened")
            # Fetch broadcast details
            result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
            broadcast = result.scalar_one_or_none()
            
            if not broadcast:
                logger.error(f"Broadcast {broadcast_id} not found")
                print(f"DEBUG: Broadcast {broadcast_id} not found")
                return

            print(f"DEBUG: Broadcast found: {broadcast}")
            # Fetch all users
            result = await session.execute(select(User.id))
            user_ids = result.scalars().all()
            print(f"DEBUG: Found {len(user_ids)} users")
            
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
                    
                    msg = None
                    if broadcast.message_type == 'text':
                        msg = await bot.send_message(chat_id=user_id, text=broadcast.message_text)
                    elif broadcast.message_type == 'photo':
                         msg = await bot.send_photo(chat_id=user_id, photo=media, caption=broadcast.message_text)
                    elif broadcast.message_type == 'video':
                         msg = await bot.send_video(chat_id=user_id, video=media, caption=broadcast.message_text)
                    elif broadcast.message_type == 'animation':
                         msg = await bot.send_animation(chat_id=user_id, animation=media, caption=broadcast.message_text)
                    
                    if msg:
                        # Save message ID for future deletion
                        bm = BroadcastMessage(broadcast_id=broadcast.id, user_id=user_id, message_id=msg.message_id)
                        session.add(bm)
                    
                    sent += 1
                except Exception as e:
                    # logger.error(f"Failed to send to {user_id}: {e}")
                    failed += 1
                
                # Rate limit
                await asyncio.sleep(0.05)
                
                # Commit periodically
                if (sent + failed) % 20 == 0:
                     await session.commit()

            # Final update
            broadcast.sent_count = sent
            broadcast.failed_count = failed
            broadcast.status = "completed"
            await session.commit()
            logger.info(f"Broadcast {broadcast_id} finished. Sent: {sent}, Failed: {failed}")
            print(f"DEBUG: Broadcast finished. Sent: {sent}, Failed: {failed}")

    except Exception as e:
        logger.error(f"CRITICAL ERROR in broadcast_worker: {e}")
        print(f"DEBUG: CRITICAL ERROR: {e}")

async def delete_broadcast_worker(broadcast_id: int):
    """
    Background task to delete broadcast messages.
    """
    logger.info(f"Deleting broadcast {broadcast_id}")
    
    async with async_session() as session:
        # Fetch all messages for this broadcast
        result = await session.execute(select(BroadcastMessage).where(BroadcastMessage.broadcast_id == broadcast_id))
        messages = result.scalars().all()
        
        deleted_count = 0
        
        for bm in messages:
            try:
                await bot.delete_message(chat_id=bm.user_id, message_id=bm.message_id)
                deleted_count += 1
            except Exception as e:
                # Message might be too old or user blocked bot
                pass
            
            await asyncio.sleep(0.03) # Rate limit for deletion
            
        logger.info(f"Deleted {deleted_count} messages for broadcast {broadcast_id}")

async def edit_broadcast_worker(broadcast_id: int, new_text: str):
    """
    Background task to edit sent broadcast messages.
    """
    logger.info(f"Editing broadcast {broadcast_id} to: {new_text[:30]}...")
    
    async with async_session() as session:
        # Update Broadcast record
        result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = result.scalar_one_or_none()
        if broadcast:
            broadcast.message_text = new_text
            await session.commit()
            
        # Fetch all messages for this broadcast
        result = await session.execute(select(BroadcastMessage).where(BroadcastMessage.broadcast_id == broadcast_id))
        messages = result.scalars().all()
        
        edited_count = 0
        
        for bm in messages:
            try:
                if broadcast.message_type == 'text':
                    await bot.edit_message_text(chat_id=bm.user_id, message_id=bm.message_id, text=new_text)
                else:
                    await bot.edit_message_caption(chat_id=bm.user_id, message_id=bm.message_id, caption=new_text)
                
                edited_count += 1
            except Exception as e:
                # Message might be too old or user blocked bot
                pass
            
            await asyncio.sleep(0.05) # Rate limit
            
        logger.info(f"Edited {edited_count} messages for broadcast {broadcast_id}")
