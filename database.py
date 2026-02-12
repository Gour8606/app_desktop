import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Database file lives alongside this script, not in the CWD
_DB_DIR = os.path.dirname(os.path.abspath(__file__))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(_DB_DIR, 'meesho_sales.db')}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite-specific configuration
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
