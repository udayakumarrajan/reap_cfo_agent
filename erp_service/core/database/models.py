from sqlalchemy import Column, String, Float, Integer, ForeignKey, Boolean, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"
    tx_id = Column(String, primary_key=True)
    external_id = Column(String, unique=True, nullable=True)
    tenant_id = Column(String, nullable=False)
    merchant = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="PENDING")
    account_code = Column(String, nullable=True)
    workflow_id = Column(String, nullable=True)
    comments = Column(String, nullable=True)
    timestamp = Column(String, default=lambda: datetime.now().isoformat())

class OutboxEntry(Base):
    __tablename__ = "outbox"
    id = Column(String, primary_key=True)
    tx_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().isoformat())

class LedgerBalance(Base):
    __tablename__ = "ledger_balances"
    tenant_id = Column(String, primary_key=True)
    account_code = Column(String, primary_key=True)
    balance = Column(Float, default=0.0)

class ChartOfAccount(Base):
    __tablename__ = "coa"
    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)


class TaggingFeedback(Base):
    """Per-tenant tagging examples from auto-post and human overrides."""
    __tablename__ = "tagging_feedback"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    merchant = Column(String, nullable=False)
    amount = Column(Float, nullable=True)
    account_code = Column(String, nullable=False)
    account_name = Column(String, nullable=True)
    source = Column(String, nullable=False)
    created_at = Column(String, default=lambda: datetime.now().isoformat())
