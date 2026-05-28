import asyncio
from typing import Optional
from loguru import logger
from temporalio.client import Client
from temporalio.worker import Worker
from workflow_service.activities.transaction_activities import TransactionActivities
from workflow_service.workflows.tagging_workflow import TransactionCloseWorkflow
from bootstrap.config import TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE

async def connect_temporal(address: str = TEMPORAL_ADDRESS) -> Optional[Client]:
    """
    Asynchronously connects to the Temporal cluster.
    Returns the Client if successful, or None if connection fails.
    """
    try:
        client = await Client.connect(address)
        logger.info(f"Connected to Temporal at {address}")
        return client
    except Exception:
        logger.warning(f"Could not connect to Temporal server at {address}.")
        return None

def start_worker_task(
    client: Client, 
    activities: TransactionActivities, 
    task_queue: str = TEMPORAL_TASK_QUEUE
) -> asyncio.Task:
    """
    Creates and schedules a Temporal worker task listening to the task queue.
    """
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[TransactionCloseWorkflow],
        activities=[
            activities.fetch_tenant_context_activity,
            activities.run_llm_tagger_activity,
            activities.post_to_accounting_system_activity,
            activities.update_learning_loop_vectors_activity,
        ],
    )
    logger.info("Starting Temporal Worker...")
    return asyncio.create_task(worker.run())
