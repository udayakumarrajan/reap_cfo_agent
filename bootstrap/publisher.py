from typing import Optional, Callable, Awaitable
from uuid import uuid4

from loguru import logger
from temporalio.client import Client
from erp_service.core.database import SqlAlchemyERP
from erp_service.core.publisher import OutboxPublisher
from erp_service.core.utils.circuit_breaker import CircuitBreaker
from workflow_service.workflows.tagging_workflow import TransactionCloseWorkflow
from bootstrap.config import TEMPORAL_TASK_QUEUE

def create_trigger_workflow_fn(
    client: Optional[Client],
    erp: SqlAlchemyERP,
    task_queue: str = TEMPORAL_TASK_QUEUE,
    failure_threshold: int = 3,
    recovery_timeout: int = 30
) -> Callable[[dict], Awaitable[None]]:
    """
    Creates a callback function that triggers a Temporal workflow, protected by a Circuit Breaker.
    """
    breaker = CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout)

    async def trigger_workflow(payload: dict) -> None:
        if not breaker.is_available():
            logger.warning(f"CircuitBreaker: Circuit is OPEN. Skipping trigger for {payload.get('tx_id')}")
            raise RuntimeError("Circuit Breaker is OPEN: Temporal is currently unreachable.")

        if not client:
            breaker.record_failure()
            raise RuntimeError("Temporal client not connected. Cannot trigger workflow.")

        tx_id = payload["tx_id"]
        existing = erp.get_transaction(tx_id)
        if existing and existing.get("workflow_id"):
            logger.info(
                f"Workflow already linked for transaction {tx_id} "
                f"(workflow_id={existing['workflow_id']}). Skipping duplicate start."
            )
            breaker.record_success()
            return

        workflow_id = str(uuid4())
        logger.info(f"Triggering workflow for transaction {tx_id} (workflow_id={workflow_id})")

        try:
            await client.start_workflow(
                TransactionCloseWorkflow.run,
                {
                    "tx_id": tx_id,
                    "tenant_id": payload["tenant_id"],
                    "payload": payload
                },
                id=workflow_id,
                task_queue=task_queue,
            )
            erp.set_workflow_id(tx_id, workflow_id)
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise e

    return trigger_workflow

def start_publisher(erp: SqlAlchemyERP, trigger_fn) -> OutboxPublisher:
    """
    Creates and returns the OutboxPublisher instance.
    The caller must run `await publisher.start()` to begin the polling loop.
    """
    return OutboxPublisher(erp, trigger_fn)
