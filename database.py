import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, pool, text, MetaData
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables
load_dotenv()
from config import config

# Create database engine with connection pooling from config
try:
    print(f"📡 Attempting to connect to database (type: {config.DATABASE_URL.split(':')[0]})")
    engine = create_engine(
        config.DATABASE_URL,
        poolclass=pool.QueuePool,
        pool_size=config.DB_POOL_SIZE,
        max_overflow=config.DB_MAX_OVERFLOW,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=config.DB_POOL_RECYCLE,
        hide_parameters=True,  # Keep participant data out of SQL error messages
        echo=False
    )
except Exception as e:
    print(f"❌ FAILED to create database engine: {e}")
    raise

# Session setup for interacting with the database
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()

# Dependency to get DB session
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def add_missing_columns(target_engine: Engine, metadata: MetaData) -> None:
    """Add nullable model columns that an existing table doesn't have yet.

    create_all() only creates missing tables, so a column added to a model would
    never reach an existing (e.g. production) database. There is no migration tool;
    this covers the simple case of new nullable columns.
    """
    inspector = inspect(target_engine)
    quote = target_engine.dialect.identifier_preparer.quote
    # Postgres lets concurrent app starts race safely; SQLite has no IF NOT EXISTS here
    if_not_exists = "IF NOT EXISTS " if target_engine.dialect.name == "postgresql" else ""

    for table in metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing or not column.nullable:
                continue
            column_type = column.type.compile(dialect=target_engine.dialect)
            ddl = f"ALTER TABLE {quote(table.name)} ADD COLUMN {if_not_exists}{quote(column.name)} {column_type}"
            try:
                with target_engine.begin() as connection:
                    connection.execute(text(ddl))
                print(f"✅ Added column {table.name}.{column.name}")
            except Exception as e:
                # DDL errors carry no participant data, so log the reason in full
                print(f"❌ Could not add column {table.name}.{column.name}: {e}")
