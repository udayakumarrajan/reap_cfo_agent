import os
import json
from typing import List, Dict, Any, Optional
from loguru import logger
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from temporalio.client import Client
from ..core.database import SqlAlchemyERP
from .dashboard import generate_dashboard_html

class TransactionRequest(BaseModel):
    merchant: str
    amount: float
    tenant_id: str = "123"
    external_id: Optional[str] = None


class ResolveRequest(BaseModel):
    account_code: str = Field(default="6200", description="Corrected chart of accounts code")


class AccountingGatewayRouter:
    """
    Mock Network Endpoint API Router for state mutation patches.
    Fetches historical context from JSON and uses a separate dashboard generator.
    """
    def __init__(self, erp: SqlAlchemyERP):
        self.erp = erp
        self._temporal_client: Optional[Client] = None
        self.app = FastAPI(title="Reap ERP Service Gateway")
        self._setup_routes()

    def set_temporal_client(self, client: Optional[Client]) -> None:
        self._temporal_client = client

    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_handler(request: Request):
            return await self.get_dashboard(request)

        @self.app.get("/api/coa/{tenant_id}")
        async def get_tenant_coa_handler(tenant_id: str):
            return await self.get_tenant_coa(tenant_id)

        @self.app.get("/api/history/{tenant_id}")
        async def get_historical_context_handler(tenant_id: str):
            return await self.get_historical_context(tenant_id)

        @self.app.post("/api/transactions")
        async def create_transaction_handler(req: TransactionRequest):
            return await self.create_transaction(req)

        @self.app.patch("/api/transactions/{tx_id}")
        async def update_ledger_status_handler(
            tx_id: str,
            status: str,
            account_code: Optional[str] = None,
            reasoning: Optional[str] = None,
        ):
            return await self.update_ledger_status(tx_id, status, account_code, reasoning)

        @self.app.post("/api/transactions/{tx_id}/resolve")
        async def resolve_transaction_handler(tx_id: str, account_code: str = Form(default="6200")):
            await self.resolve_transaction(tx_id, account_code)
            tx = self.erp.get_transaction(tx_id)
            tenant = tx.get("tenant_id", "all") if tx else "all"
            return RedirectResponse(url=f"/?tenant_id={tenant}", status_code=303)

    async def get_dashboard(self, request: Request):
        tenant_id = request.query_params.get("tenant_id", "all")
        unique_tenants = self.erp.get_unique_tenants()
        if "123" not in unique_tenants:
            unique_tenants = ["123"] + unique_tenants
        return generate_dashboard_html(
            self.erp.transactions,
            self.erp.get_ledger_balances_for_view(tenant_id),
            self.erp.count_pending_outbox(tenant_id),
            selected_tenant=tenant_id,
            unique_tenants=unique_tenants,
        )

    async def get_tenant_coa(self, tenant_id: str):
        coa = self.erp.get_coa(tenant_id)
        return JSONResponse(content=coa)

    async def get_historical_context(self, tenant_id: str):
        logger.info(f"API CALL: Fetching historical context for tenant {tenant_id}")
        history = self._load_history()
        return JSONResponse(content=history)

    async def create_transaction(self, req: TransactionRequest):
        logger.info(f"API CALL: Creating transaction for {req.merchant} (${req.amount})")
        tx_id = self.erp.create_transaction(req.tenant_id, {
            "merchant": req.merchant,
            "amount": req.amount,
            "external_id": req.external_id,
        })
        return JSONResponse(content={"status": "success", "tx_id": tx_id})

    async def update_ledger_status(
        self,
        tx_id: str,
        status: str,
        account_code: Optional[str] = None,
        reasoning: Optional[str] = None,
    ):
        logger.info(f"API CALL: Updating status for {tx_id} to {status} (Code: {account_code})")
        self.erp.update_transaction_status(tx_id, status, account_code, reasoning)
        return JSONResponse(content={"status": "success", "tx_id": tx_id})

    async def resolve_transaction(self, tx_id: str, account_code: str):
        tx = self.erp.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction {tx_id} not found")
        if tx.get("status") != "NEEDS_REVIEW":
            raise HTTPException(
                status_code=400,
                detail=f"Transaction {tx_id} is not awaiting review (status={tx.get('status')})",
            )
        workflow_id = tx.get("workflow_id")
        if not workflow_id:
            raise HTTPException(status_code=400, detail="No workflow_id linked to this transaction")
        if not self._temporal_client:
            raise HTTPException(status_code=503, detail="Temporal client not connected")

        from workflow_service.workflows.tagging_workflow import TransactionCloseWorkflow
        handle = self._temporal_client.get_workflow_handle(workflow_id)
        await handle.signal(
            TransactionCloseWorkflow.human_override_signal,
            {"account_code": account_code},
        )
        logger.info(f"Signaled workflow {workflow_id} for {tx_id} -> {account_code}")
        return JSONResponse(content={
            "status": "signaled",
            "tx_id": tx_id,
            "workflow_id": workflow_id,
            "account_code": account_code,
        })

    def _load_history(self) -> List[Dict[str, Any]]:
        history_path = os.path.join(os.path.dirname(__file__), "..", "mock_data", "history.json")
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Router: Failed to load history from {history_path}: {e}")
            return []
