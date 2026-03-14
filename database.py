import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL is not set in environment variables!")
    raise ValueError("DATABASE_URL environment variable is not set")

print(f"📡 Attempting to connect to database (type: {DATABASE_URL.split(':')[0]})")

try:
    # Create database engine with connection pooling
    engine = create_engine(
        DATABASE_URL,
        poolclass=pool.QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=False  # Set to True for SQL debugging
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