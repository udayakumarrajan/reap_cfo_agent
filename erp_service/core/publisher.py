import asyncio
import json
from typing import Callable, Awaitable, Optional
from loguru import logger
from .database import SqlAlchemyERP

class OutboxPublisher:
    """
    Background thread enforcing At-Least-Once Delivery to Workflows.
    Uses an asyncio.Event for immediate triggering when new entries arrive.
    """
    def __init__(self, erp: SqlAlchemyERP, trigger_fn: Callable[[dict], Awaitable[None]], poll_interval: float = 5.0):
        self.erp = erp
        self.trigger_fn = trigger_fn
        self.poll_interval = poll_interval
        self._running = False
        self._trigger_event = asyncio.Event()
        
        # Link database notification skip to our trigger event
        self.erp.on_new_entry = self.notify

    def notify(self):
        """Called by the database when a new entry is added."""
        logger.info("OutboxPublisher: Received notification of new entry.")
        self._trigger_event.set()

    async def start(self):
        self._running = True
        logger.info("OutboxPublisher: Starting event-driven loop.")
        while self._running:
            try:
                await self._process_outbox()
            except Exception as e:
                logger.error(f"OutboxPublisher: Error in processing loop: {e}")
            
            # Reset event and wait for next trigger or timeout
            try:
                await asyncio.wait_for(self._trigger_event.wait(), timeout=self.poll_interval)
                self._trigger_event.clear()
                logger.info("OutboxPublisher: Waking up for new entries.")
            except asyncio.TimeoutError:
                pass

    def stop(self):
        self._running = False
        self._trigger_event.set() # Wake up to stop
        logger.info("OutboxPublisher: Stopping processing loop.")

    async def _process_outbox(self):
        pending_entries = self.erp.outbox_table
        
        if not pending_entries:
            return

        logger.info(f"OutboxPublisher: Processing {len(pending_entries)} pending entries.")
        
        for entry in pending_entries:
            try:
                payload = entry["payload"]
                await self.trigger_fn(payload)
                self.erp.mark_outbox_processed(entry["id"])
                logger.success(f"OutboxPublisher: Successfully triggered workflow for {entry['tx_id']}")
            except Exception as e:
                logger.error(f"OutboxPublisher: Failed to trigger workflow for {entry['tx_id']}: {e}")
