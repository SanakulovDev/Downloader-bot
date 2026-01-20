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

async def delete_broadcast_worker(broadcast_id: int, delete_record: bool = False):
    """
    Background task to delete broadcast messages.
    If delete_record is True, also deletes the broadcast record from DB after messages.
    """
    logger.info(f"Deleting broadcast {broadcast_id} (Record delete: {delete_record})")
    
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

        if delete_record:
            # Delete the broadcast record itself
            result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
            broadcast = result.scalar_one_or_none()
            if broadcast:
                await session.delete(broadcast)
                await session.commit()
                logger.info(f"Deleted broadcast record {broadcast_id} from DB")

async def edit_broadcast_worker(broadcast_id: int, new_text: str, new_type: str = None, new_file_id: str = None):
    """
    Background task to edit sent broadcast messages.
    Supports:
    1. Text edit (if type is same)
    2. Media edit (if type supports it via edit_message_media) - simplified to delete/resend if needed
    3. Type change (Delete + Send new)
    """
    logger.info(f"Editing broadcast {broadcast_id}...")
    
    async with async_session() as session:
        # Update Broadcast record
        result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = result.scalar_one_or_none()
        
        if not broadcast:
            return

        old_type = broadcast.message_type
        
        # Update DB fields
        broadcast.message_text = new_text
        if new_type:
             broadcast.message_type = new_type
        if new_file_id:
             broadcast.file_id = new_file_id
             
        await session.commit()
        
        # Determine strategy
        # Strategy A: Simple Text Edit (Same type, Text only)
        # Strategy B: Full Replace (Type changed OR Media changed) -> Delete + Send
        
        mode = 'text_edit'
        if new_type and new_type != old_type:
            mode = 'replace'
        elif new_file_id and new_file_id != broadcast.file_id:
             mode = 'replace'
        
        # Fetch all messages
        result = await session.execute(select(BroadcastMessage).where(BroadcastMessage.broadcast_id == broadcast_id))
        messages = result.scalars().all()
        
        edited_count = 0
        
        # Prepare media for replace mode
        media_obj = None
        if mode == 'replace':
             media_path = broadcast.file_id
             if media_path and (media_path.startswith("/app/") or media_path.startswith(".") or "/" in media_path):
                 from aiogram.types import FSInputFile
                 import os
                 if os.path.exists(media_path):
                     media_obj = FSInputFile(media_path)
                 else:
                     media_obj = media_path # Fallback to ID
             else:
                 media_obj = media_path

        for bm in messages:
            try:
                if mode == 'text_edit':
                    if broadcast.message_type == 'text':
                        await bot.edit_message_text(chat_id=bm.user_id, message_id=bm.message_id, text=new_text)
                    else:
                        await bot.edit_message_caption(chat_id=bm.user_id, message_id=bm.message_id, caption=new_text)
                
                elif mode == 'replace':
                    # 1. Delete old
                    try:
                        await bot.delete_message(chat_id=bm.user_id, message_id=bm.message_id)
                    except:
                        pass # Message might be old
                    
                    # 2. Send new
                    msg = None
                    if broadcast.message_type == 'text':
                        msg = await bot.send_message(chat_id=bm.user_id, text=broadcast.message_text)
                    elif broadcast.message_type == 'photo':
                         # Re-create FSInputFile for each send if strictly needed, or reuse? 
                         # aiogram FSInputFile can be reused usually but safer to re-init if stream closed
                         curr_media = media_obj
                         if hasattr(media_obj, 'path'): # Is FSInputFile
                             from aiogram.types import FSInputFile
                             curr_media = FSInputFile(media_obj.path)
                             
                         msg = await bot.send_photo(chat_id=bm.user_id, photo=curr_media, caption=broadcast.message_text)
                    elif broadcast.message_type == 'video':
                         curr_media = media_obj
                         if hasattr(media_obj, 'path'):
                             from aiogram.types import FSInputFile
                             curr_media = FSInputFile(media_obj.path)
                         msg = await bot.send_video(chat_id=bm.user_id, video=curr_media, caption=broadcast.message_text)
                    elif broadcast.message_type == 'animation':
                         curr_media = media_obj
                         if hasattr(media_obj, 'path'):
                             from aiogram.types import FSInputFile
                             curr_media = FSInputFile(media_obj.path)
                         msg = await bot.send_animation(chat_id=bm.user_id, animation=curr_media, caption=broadcast.message_text)

                    # Update Message ID in DB
                    if msg:
                        bm.message_id = msg.message_id
            
                edited_count += 1
            except Exception as e:
                # logger.error(f"Edit failed for {bm.user_id}: {e}")
                pass
            
            await asyncio.sleep(0.05) # Rate limit
            
        # Commit updated message IDs if replaced
        if mode == 'replace':
            await session.commit()
            
        logger.info(f"Edited {edited_count} messages for broadcast {broadcast_id} (Mode: {mode})")
