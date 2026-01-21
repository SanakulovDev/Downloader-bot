import asyncio
import logging
import os
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.download import download_video, download_audio

logger = logging.getLogger(__name__)

# Queue settings
DOWNLOAD_QUEUE = asyncio.Queue()
MAX_CONCURRENT_DOWNLOADS = 2

async def process_video_task(chat_id, url, msgs):
    # Backward compatibility or dict check
    if isinstance(msgs, dict):
        user_msg = msgs.get('user_msg')
        status_msg = msgs.get('status_msg')
    else:
        user_msg = msgs
        status_msg = None

    video_path = None
    try:
        video_path = await download_video(url, chat_id)
        if video_path:
            await user_msg.reply_video(
                FSInputFile(video_path),
                caption="🤖 " + (os.getenv("TELEGRAM_NICKNAME") or "@InstantAudioBot")
            )
            
            # Delete status message if present
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
        else:
            await user_msg.reply("❌ Video yuklab bo'lmadi.")
            if status_msg:
                try:
                    await status_msg.delete()
                except:
                    pass
    except Exception as e:
        logger.error(f"Video task error: {e}")
        # Send the actual error message if it's one of ours, otherwise generic
        err_text = str(e)
        if "❌" not in err_text:
             err_text = "❌ Yuklashda xatolik yuz berdi! (Keyinroq urinib ko'ring)"
             
        await user_msg.reply(err_text)
        
        if status_msg:
            try:
                await status_msg.delete()
            except:
                pass
    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                logger.info(f"Deleted temp file: {video_path}")
            except Exception as e:
                logger.error(f"Error deleting file {video_path}: {e}")

async def process_music_task(chat_id, video_id, callback: CallbackQuery):
    try:
        await callback.message.edit_text("⏳ <b>Yuklanmoqda...</b>", parse_mode='HTML')
    except:
        pass

    audio_path = None
    try:
        audio_path, filename = await download_audio(video_id, chat_id)
        if audio_path:
            # Like button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❤️ Sevimlilarga qo'shish", callback_data=f"like:{video_id}")]
            ])
            
            await callback.message.answer_audio(
                FSInputFile(audio_path, filename=filename),
                caption=f"🎵 {filename.replace('.m4a', '')} \n🤖 @qishloqlik_devbot",
                title=filename.replace('.m4a', ''),
                reply_markup=keyboard
            )
            try:
                await callback.message.delete()
            except:
                pass
        else:
            await callback.message.edit_text("❌ Musiqa yuklashda xatolik bo'ldi.")
    except Exception as e:
        logger.error(f"Music task error: {e}")
        
        err_text = str(e)
        if "❌" not in err_text:
             err_text = "❌ Yuborishda xatolik yuz berdi!"
             
        await callback.message.answer(err_text)
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Deleted temp file: {audio_path}")
            except Exception as e:
                logger.error(f"Error deleting file {audio_path}: {e}")

async def download_worker(worker_id: int):
    logger.info(f"Worker {worker_id} started")
    while True:
        try:
            # Task format: (type, chat_id, data, message/callback)
            task = await DOWNLOAD_QUEUE.get()
            task_type, chat_id, data, msg_obj = task
            
            queue_size = DOWNLOAD_QUEUE.qsize()
            logger.info(f"Worker {worker_id} processing task. Queue size: {queue_size}")
            
            try:
                if task_type == 'video':
                    await process_video_task(chat_id, data, msg_obj)
                elif task_type == 'music':
                    await process_music_task(chat_id, data, msg_obj)
            except Exception as e:
                logger.error(f"Error processing task in worker {worker_id}: {e}")
                try:
                    if isinstance(msg_obj, dict):
                        target = msg_obj.get('user_msg')
                    elif isinstance(msg_obj, CallbackQuery):
                        target = msg_obj.message
                    else:
                        target = msg_obj
                        
                    if target:
                        await target.answer("❌ Xatolik yuz berdi.")
                except:
                    pass
            finally:
                DOWNLOAD_QUEUE.task_done()
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")
            await asyncio.sleep(1)

async def start_workers():
    workers = []
    for i in range(MAX_CONCURRENT_DOWNLOADS):
        w = asyncio.create_task(download_worker(i+1))
        workers.append(w)
    return workers
