from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _make_engine() -> tuple[object, async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


_engine, _AsyncSessionLocal = _make_engine()


def get_engine() -> object:
    return _engine


async def get_db() -> AsyncIterator[AsyncSession]:
    async with _AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
