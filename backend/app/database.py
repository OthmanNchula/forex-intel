from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Convert the Supabase URL to work with psycopg2
# Supabase gives postgresql:// but SQLAlchemy needs postgresql+psycopg2://
DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+psycopg2://"
)

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # test connection before using it
    pool_size=5,              # max 5 connections in pool
    max_overflow=10,          # allow 10 extra connections under load
    echo=settings.ENVIRONMENT == "development",  # log SQL in dev mode
)

# Each request gets its own database session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for all our ORM models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency — yields a DB session per request,
    closes it automatically when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()