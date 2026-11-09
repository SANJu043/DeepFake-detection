"""
Alembic environment script.

Supports both offline (SQL script generation) and online (live DB) migration
modes with an async SQLAlchemy engine (asyncpg driver).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# ---------------------------------------------------------------------------
# Load our ORM Base and all models so Alembic can inspect metadata
# ---------------------------------------------------------------------------
from backend.app.core.database import Base  # noqa: F401 – registers Base
from backend.app.models.models import (  # noqa: F401 – registers all tables
    AnomalyEventRecord,
    Attestation,
    AuditLog,
    Job,
    Revocation,
    Share,
    User,
    Video,
)
from backend.app.config import get_settings

# ---------------------------------------------------------------------------
# Alembic Config object – gives access to the values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_url() -> str:
    """Return the synchronous database URL for Alembic.

    We read from our Settings (which load .env / environment variables) so
    the URL is never hard-coded.  Alembic needs the plain ``postgresql://``
    scheme (not ``+asyncpg``) for its internal connection handling; the async
    engine is created separately in ``run_async_migrations``.
    """
    settings = get_settings()
    return settings.database_url  # postgresql://user:pass@host:port/db


# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well.  By skipping the Engine creation we
    don't even need a DBAPI to be available.

    Calls to ``context.execute()`` here emit the given string to the script
    output.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online (async) mode
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    """Execute migrations synchronously on an open connection.

    This is called via ``run_sync`` from within an async context so that
    Alembic's (synchronous) migration runner can use the live connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through ``run_sync``."""
    settings = get_settings()
    connectable: AsyncEngine = create_async_engine(
        settings.async_database_url,  # postgresql+asyncpg://...
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
