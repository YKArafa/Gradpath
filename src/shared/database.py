import os
import sys
import asyncio
import re
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Load environment variables
load_dotenv()

# Psycopg 3 async requires WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgresql:"):
    DATABASE_URL = re.sub(r"^postgresql:", "postgresql+psycopg:", DATABASE_URL)

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True)


from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from src.shared.models import Base

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


def get_engine() -> AsyncEngine:
    return engine


async def get_session() -> AsyncSession:
    """Dependency / generator for async session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables registered with Base.metadata if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE degree ADD COLUMN IF NOT EXISTS courses JSONB NOT NULL DEFAULT '[]'::jsonb;")
        )
        await conn.execute(
            text("ALTER TABLE course ADD COLUMN IF NOT EXISTS difficulty_level VARCHAR(20) NOT NULL DEFAULT 'medium';")
        )


async def async_main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("select 'hello world'"))
        print(result.fetchall())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(async_main())