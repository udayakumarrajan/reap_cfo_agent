import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

def _migrate_schema(engine) -> None:
    """Apply lightweight SQLite migrations for columns added after first deploy."""
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    if "transactions" not in insp.get_table_names():
        return
    columns = {c["name"] for c in insp.get_columns("transactions")}
    if "workflow_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN workflow_id VARCHAR"))

def create_db_engine(db_url: str = None):
    if db_url is None:
        db_url = os.getenv("DATABASE_URL", "sqlite:///ledger.db")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _migrate_schema(engine)
    return engine

def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
