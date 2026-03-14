import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

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