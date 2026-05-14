from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, MetaData, String, Table, Column, Text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.sql import func

from crawler.config import get_settings

metadata = MetaData()

flight_offers = Table(
    "flight_offers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("origin", String(3), nullable=False, index=True),
    Column("destination", String(3), nullable=False, index=True),
    Column("departure_date", String(10), nullable=False, index=True),
    Column("return_date", String(10), nullable=True),
    Column("price", Float, nullable=True),
    Column("currency", String(3), nullable=False, default="BRL"),
    Column("source_site", String(100), nullable=False, default="cvc.com.br"),
    Column("source_url", Text, nullable=True),
    Column("collected_at", DateTime, nullable=False, default=datetime.utcnow, server_default=func.now(), index=True),
)


def normalize_database_url(database_url: str) -> str:
    """Normaliza a URL de banco para o driver async do SQLAlchemy."""

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return database_url


def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        normalize_database_url(settings.database_url),
        pool_pre_ping=True,
        future=True,
    )


async def init_db() -> None:
    """Cria as tabelas necessárias caso ainda não existam."""

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    await engine.dispose()


def get_session_factory() -> async_sessionmaker:
    engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False)
