import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from utils.db_api.database import engine
from sqlalchemy import text

async def upgrade():
    async with engine.begin() as conn:
        try:
            print("Adding language column to users table...")
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR"))
            print("Done!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(upgrade())
