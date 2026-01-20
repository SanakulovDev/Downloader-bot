from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from typing import Callable, Dict, Any, Awaitable
from sqlalchemy import update
from sqlalchemy.future import select
from utils.db_api.database import async_session
from utils.db_api.models import User as DBUser
import logging

class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")

        if user:
            # We don't want to block the main handler, so we can potentially run this as a background task
            # But for simplicity and reliability, we'll do a quick update.
            # To avoid DB spam, we could use Redis to debounce, but for now direct update is fine for moderate loads.
            
            try:
                async with async_session() as session:
                    # Method 1: Update if exists (Efficient)
                    # We assume user exists because registration check usually happens before or we upsert.
                    # Simple Upsert:
                    stmt = select(DBUser).where(DBUser.id == user.id)
                    result = await session.execute(stmt)
                    db_user = result.scalar_one_or_none()
                    
                    if db_user:
                        from sqlalchemy import func
                        db_user.last_active = func.now()
                        await session.commit()
            except Exception as e:
                logging.error(f"Failed to update activity for user {user.id}: {e}")

        return await handler(event, data)
