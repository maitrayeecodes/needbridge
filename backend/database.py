"""PostgreSQL connection/session setup. Import lazily so the legacy demo can still run."""
import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@lru_cache(maxsize=1)
def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured. Set it to a PostgreSQL connection string.")
    # Render/managed providers commonly supply postgres:// or postgresql:// URLs.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
