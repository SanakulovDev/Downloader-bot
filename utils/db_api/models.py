from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False) # Telegram ID
    full_name: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, full_name='{self.full_name}')>"

class Broadcast(Base):
    __tablename__ = 'broadcasts'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_text: Mapped[str] = mapped_column(String, nullable=True)
    message_type: Mapped[str] = mapped_column(String, default="text") # text, photo, video, animation
    file_id: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending") # pending, processing, completed, failed
    total_users: Mapped[int] = mapped_column(BigInteger, default=0)
    sent_count: Mapped[int] = mapped_column(BigInteger, default=0)
    failed_count: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Broadcast(id={self.id}, status='{self.status}')>"

class BroadcastMessage(Base):
    __tablename__ = 'broadcast_messages'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(BigInteger) # FK logic handled manually or via simple column for now
    user_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)

    def __repr__(self):
        return f"<BroadcastMessage(broadcast_id={self.broadcast_id}, message_id={self.message_id})>"
