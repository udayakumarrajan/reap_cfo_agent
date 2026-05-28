import asyncio
from loguru import logger
from workflow_service.activities.transaction_activities import TransactionActivities
from bootstrap.config import DATABASE_URL, ERP_HOST, ERP_PORT, TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE
from bootstrap.db import init_db
from bootstrap.server import create_router, start_dashboard_thread
from bootstrap.temporal import connect_temporal, start_worker_task
from bootstrap.publisher import create_trigger_workflow_fn, start_publisher

async def run():
    """
    Orchestrates the bootstrapping of ERP database, API Gateway Server, Outbox Publisher,
    and Temporal Worker into a single operational system.
    """
    logger.info("Starting System Bootstrapping...")

    erp = init_db(DATABASE_URL)

    client = await connect_temporal(TEMPORAL_ADDRESS)

    erp_router = create_router(erp)
    erp_router.set_temporal_client(client)

    activities = TransactionActivities(erp_router)
    trigger_fn = create_trigger_workflow_fn(client, erp, TEMPORAL_TASK_QUEUE)

    start_dashboard_thread(erp_router, ERP_HOST, ERP_PORT)

    publisher = start_publisher(erp, trigger_fn)
    publisher_task = asyncio.create_task(publisher.start())

    worker_task = None
    if client:
        worker_task = start_worker_task(client, activities, TEMPORAL_TASK_QUEUE)

    logger.info("System fully operational.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received. Cleaning up resources...")
        publisher.stop()
        try:
            await publisher_task
        except Exception as e:
            logger.error(f"Error during OutboxPublisher shutdown: {e}")

        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error during Temporal worker shutdown: {e}")

        logger.info("System shutdown complete.")
