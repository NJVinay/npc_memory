from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# PostgreSQL Database URL - Replace with your actual database credentials
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/npc_memory_db"

# Create database engine
engine = create_engine(DATABASE_URL)

# Session setup for interacting with the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()