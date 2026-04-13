"""Async SQLAlchemy database session management."""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tirithel.config.settings import get_settings

settings = get_settings()

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.database.url.replace("sqlite+aiosqlite:///", "")) or ".", exist_ok=True)

engine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency that provides an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables. Used for development/MVP."""
    from tirithel.domain.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
