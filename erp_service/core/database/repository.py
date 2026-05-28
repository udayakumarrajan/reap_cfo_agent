import uuid
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session
from .models import Transaction, OutboxEntry, LedgerBalance, ChartOfAccount, TaggingFeedback
from ..seeds import DEFAULT_COA, DEFAULT_TENANT_ID, DEFAULT_TAGGING_EXAMPLES
from loguru import logger


class SqlAlchemyERP:
    """SQLAlchemy-backed ERP implementation."""

    def __init__(self, session_factory, on_new_entry: Optional[Callable[[], None]] = None):
        self.session_factory = session_factory
        self.on_new_entry = on_new_entry
        self._seed_default_coa()
        self._seed_cold_start_examples()

    def _seed_default_coa(self) -> None:
        with self.session_factory() as session:
            if session.query(ChartOfAccount).count() > 0:
                return
            for item in DEFAULT_COA:
                session.add(ChartOfAccount(
                    code=item["code"],
                    name=item["name"],
                    type=item["type"],
                ))
                session.add(LedgerBalance(
                    tenant_id=DEFAULT_TENANT_ID,
                    account_code=item["code"],
                    balance=0.0,
                ))
            session.commit()
            logger.info("ORM: Seeded default chart of accounts.")

    def _seed_cold_start_examples(self) -> None:
        with self.session_factory() as session:
            if session.query(TaggingFeedback).count() > 0:
                return
            for ex in DEFAULT_TAGGING_EXAMPLES:
                session.add(TaggingFeedback(
                    id=str(uuid.uuid4()),
                    tenant_id=DEFAULT_TENANT_ID,
                    merchant=ex["merchant"],
                    amount=ex["amount"],
                    account_code=ex["account_code"],
                    account_name=ex["account_name"],
                    source=ex["source"],
                ))
            session.commit()
            logger.info("ORM: Seeded cold-start tagging examples for tenant %s.", DEFAULT_TENANT_ID)

    def _adjust_balance(self, session: Session, tenant_id: str, account_code: str, delta: float) -> None:
        bal = session.query(LedgerBalance).filter_by(
            tenant_id=tenant_id, account_code=account_code
        ).first()
        if bal:
            bal.balance += delta
        else:
            session.add(LedgerBalance(
                tenant_id=tenant_id, account_code=account_code, balance=delta
            ))

    def _account_name(self, session: Session, account_code: str) -> Optional[str]:
        row = session.query(ChartOfAccount).filter_by(code=account_code).first()
        return row.name if row else None

    def create_transaction(self, tenant_id: str, payload: Dict[str, Any]) -> str:
        external_id = payload.get("external_id")

        with self.session_factory() as session:
            if external_id:
                existing = session.query(Transaction).filter_by(external_id=external_id).first()
                if existing:
                    return existing.tx_id

            tx_count = session.query(Transaction).count()
            tx_id = f"tx_{tx_count + 1}"

            new_tx = Transaction(
                tx_id=tx_id,
                external_id=external_id,
                tenant_id=tenant_id,
                merchant=payload["merchant"],
                amount=payload["amount"],
                status="PENDING",
            )
            session.add(new_tx)

            outbox = OutboxEntry(
                id=str(uuid.uuid4()),
                tx_id=tx_id,
                tenant_id=tenant_id,
                payload={
                    "tx_id": tx_id,
                    "external_id": external_id,
                    "tenant_id": tenant_id,
                    "merchant": payload["merchant"],
                    "amount": payload["amount"],
                    "status": "PENDING",
                },
            )
            session.add(outbox)
            session.commit()
            logger.info(f"ORM: Transaction {tx_id} created.")

        if self.on_new_entry:
            self.on_new_entry()
        return tx_id

    def set_workflow_id(self, tx_id: str, workflow_id: str) -> None:
        with self.session_factory() as session:
            tx = session.query(Transaction).filter_by(tx_id=tx_id).first()
            if tx:
                tx.workflow_id = workflow_id
                session.commit()

    def get_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        with self.session_factory() as session:
            row = session.query(Transaction).filter_by(tx_id=tx_id).first()
            if not row:
                return None
            return self._tx_to_dict(row)

    def update_transaction_status(
        self,
        tx_id: str,
        status: str,
        account_code: Optional[str] = None,
        reasoning: Optional[str] = None,
    ):
        with self.session_factory() as session:
            tx = session.query(Transaction).filter_by(tx_id=tx_id).first()
            if not tx:
                return

            old_code = tx.account_code
            tx.status = status

            if account_code is not None and account_code != old_code:
                if old_code:
                    self._adjust_balance(session, tx.tenant_id, old_code, -tx.amount)
                self._adjust_balance(session, tx.tenant_id, account_code, tx.amount)
                tx.account_code = account_code

            if reasoning:
                tx.comments = reasoning

            session.commit()
            logger.info(f"ORM: Updated {tx_id} to {status} (account {tx.account_code}).")

            if account_code and status in ("AUTO_POSTED", "HUMAN_RESOLVED"):
                self._record_tagging_feedback_in_session(
                    session,
                    tenant_id=tx.tenant_id,
                    merchant=tx.merchant,
                    amount=tx.amount,
                    account_code=account_code,
                    source="auto_posted" if status == "AUTO_POSTED" else "human_override",
                )
                session.commit()

    def _record_tagging_feedback_in_session(
        self,
        session: Session,
        tenant_id: str,
        merchant: str,
        amount: Optional[float],
        account_code: str,
        source: str,
    ) -> None:
        session.add(TaggingFeedback(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            merchant=merchant,
            amount=amount,
            account_code=account_code,
            account_name=self._account_name(session, account_code),
            source=source,
        ))

    def get_tagging_history(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Tenant-scoped few-shot examples for the classifier."""
        with self.session_factory() as session:
            rows = (
                session.query(TaggingFeedback)
                .filter_by(tenant_id=tenant_id)
                .order_by(TaggingFeedback.created_at.desc())
                .limit(limit)
                .all()
            )
            if rows:
                return [
                    {
                        "merchant": r.merchant,
                        "amount": r.amount,
                        "account_code": r.account_code,
                        "account_name": r.account_name or r.account_code,
                    }
                    for r in rows
                ]

            tx_rows = (
                session.query(Transaction)
                .filter(
                    Transaction.tenant_id == tenant_id,
                    Transaction.status.in_(("AUTO_POSTED", "HUMAN_RESOLVED")),
                    Transaction.account_code.isnot(None),
                )
                .order_by(Transaction.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "merchant": r.merchant,
                    "amount": r.amount,
                    "account_code": r.account_code,
                    "account_name": self._account_name(session, r.account_code) or r.account_code,
                }
                for r in tx_rows
            ]

    def get_coa(self, tenant_id: str) -> List[Dict[str, str]]:
        with self.session_factory() as session:
            rows = session.query(ChartOfAccount).all()
            return [{"code": r.code, "name": r.name, "type": r.type} for r in rows]

    def get_ledger_balances(self, tenant_id: str) -> Dict[str, float]:
        with self.session_factory() as session:
            coa_rows = session.query(ChartOfAccount).all()
            balances = {r.code: 0.0 for r in coa_rows}
            rows = session.query(LedgerBalance).filter_by(tenant_id=tenant_id).all()
            for r in rows:
                balances[r.account_code] = r.balance
            return balances

    def get_ledger_balances_for_view(self, tenant_id: str) -> Dict[str, float]:
        with self.session_factory() as session:
            coa_rows = session.query(ChartOfAccount).all()
            balances = {r.code: 0.0 for r in coa_rows}

            if tenant_id == "all":
                rows = session.query(LedgerBalance).all()
            else:
                rows = session.query(LedgerBalance).filter_by(tenant_id=tenant_id).all()

            for r in rows:
                balances[r.account_code] = balances.get(r.account_code, 0.0) + r.balance
            return balances

    def get_unique_tenants(self) -> List[str]:
        with self.session_factory() as session:
            balances_tenants = session.query(LedgerBalance.tenant_id).distinct().all()
            tx_tenants = session.query(Transaction.tenant_id).distinct().all()
            tenants = set([t[0] for t in balances_tenants] + [t[0] for t in tx_tenants])
            return sorted(list(tenants))

    def count_pending_outbox(self, tenant_id: str = "all") -> int:
        with self.session_factory() as session:
            q = session.query(OutboxEntry).filter_by(processed=False)
            if tenant_id != "all":
                q = q.filter_by(tenant_id=tenant_id)
            return q.count()

    @staticmethod
    def _tx_to_dict(r: Transaction) -> Dict[str, Any]:
        return {
            "tx_id": r.tx_id,
            "external_id": r.external_id,
            "tenant_id": r.tenant_id,
            "merchant": r.merchant,
            "amount": r.amount,
            "status": r.status,
            "account_code": r.account_code,
            "workflow_id": r.workflow_id,
            "comments": r.comments,
            "timestamp": r.timestamp,
        }

    @property
    def transactions(self) -> Dict[str, Dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.query(Transaction).all()
            return {r.tx_id: self._tx_to_dict(r) for r in rows}

    @property
    def outbox_table(self) -> List[Dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.query(OutboxEntry).filter_by(processed=False).all()
            return [{
                "id": r.id, "tx_id": r.tx_id, "tenant_id": r.tenant_id,
                "payload": r.payload, "processed": r.processed,
            } for r in rows]

    def mark_outbox_processed(self, entry_id: str):
        with self.session_factory() as session:
            entry = session.query(OutboxEntry).filter_by(id=entry_id).first()
            if entry:
                entry.processed = True
                session.commit()
