"""
Database Operations

This module provides database connectivity and session management.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings

async_engine = create_async_engine(
    settings.DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,  # set False to hide SQL output
)

async_session_factory = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    For ORM usage: provides a SQLAlchemy AsyncSession.
    Manages commit/rollback and closing.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
