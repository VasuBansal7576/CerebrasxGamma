from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, override

from fastapi import Depends
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from quotesquad.config import Settings


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    quote_type: Mapped[str] = mapped_column(String(32), index=True)
    vendor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    consent_to_learn: Mapped[bool] = mapped_column(default=False)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class FeedbackRecord(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(32), index=True)
    outcome: Mapped[str] = mapped_column(String(40), index=True)
    negotiated_savings: Mapped[str] = mapped_column(String(32))
    categories: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class PricingObservationRecord(Base):
    __tablename__ = "pricing_observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(32), index=True)
    quote_type: Mapped[str] = mapped_column(String(32), index=True)
    zip_prefix: Mapped[str] = mapped_column(String(5), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    amount: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class WhiteLabelRecord(Base):
    __tablename__ = "white_labels"

    organization_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text)


@dataclass(frozen=True, slots=True)
class DatabaseNotConfiguredError(RuntimeError):
    @override
    def __str__(self) -> str:
        return "database session factory is not configured"


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def configure_database(settings: Settings) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise DatabaseNotConfiguredError
    async with _session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
