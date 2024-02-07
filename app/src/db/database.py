from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

import os

# DATABASE_PATH = "sqlite+aiosqlite:///:memory:"
DATABASE_PATH = f"sqlite+aiosqlite:///{os.environ.get('DB_PATH', 'app/data/data.db')}"

engine = create_async_engine(
    DATABASE_PATH
)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass