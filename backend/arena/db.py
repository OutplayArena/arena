import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://outplaylabs-arena:outplaylabs-arena@localhost:5432/outplaylabs-arena",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20, max_overflow=30)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
