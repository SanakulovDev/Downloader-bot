from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timezone
import random
from sqlalchemy.future import select
from utils.db_api.database import async_session
from utils.db_api.models import User as DBUser
from loader import redis_client
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
            try:
                if redis_client:
                    now = datetime.now(timezone.utc).timestamp()
                    last_active_key = f"user:last_active:{user.id}"
                    await redis_client.set(last_active_key, now)

                    ttl = 600 + random.randint(0, 120)
                    lock_key = f"user:last_active:lock:{user.id}"
                    acquired = await redis_client.set(lock_key, "1", nx=True, ex=ttl)
                    if acquired:
                        async with async_session() as session:
                            stmt = select(DBUser).where(DBUser.id == user.id)
                            result = await session.execute(stmt)
                            db_user = result.scalar_one_or_none()
                            if db_user:
                                cached_ts = await redis_client.get(last_active_key)
                                if cached_ts:
                                    cached_dt = datetime.fromtimestamp(float(cached_ts), tz=timezone.utc)
                                    db_user.last_active = cached_dt
                                else:
                                    db_user.last_active = datetime.now(timezone.utc)
                                await session.commit()
                else:
                    async with async_session() as session:
                        stmt = select(DBUser).where(DBUser.id == user.id)
                        result = await session.execute(stmt)
                        db_user = result.scalar_one_or_none()
                        if db_user:
                            db_user.last_active = datetime.now(timezone.utc)
                            await session.commit()
            except Exception as e:
                logging.error(f"Failed to update activity for user {user.id}: {e}")

        return await handler(event, data)
