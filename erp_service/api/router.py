from typing import Dict, Any, Optional
from loguru import logger
from fastapi import FastAPI, Request, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from scalar_fastapi import Theme, get_scalar_api_reference
from temporalio.client import Client
from ..core.database import SqlAlchemyERP
from .dashboard import generate_dashboard_html
from .health import HealthResponse, build_health_response

API_VERSION = "0.1.0"
API_DESCRIPTION = (
    "Reap CFO Agent ERP gateway: transaction ingest, chart of accounts, "
    "tenant tagging history, ledger updates, and human-in-the-loop resolve."
)


class TransactionRequest(BaseModel):
    merchant: str
    amount: float
    tenant_id: str = "123"
    external_id: Optional[str] = None


class ResolveRequest(BaseModel):
    account_code: str = Field(default="6200", description="Corrected chart of accounts code")


class AccountingGatewayRouter:
    """ERP HTTP gateway: ledger mutations, tenant tagging history, and dashboard."""

    def __init__(self, erp: SqlAlchemyERP):
        self.erp = erp
        self._temporal_client: Optional[Client] = None
        self.app = FastAPI(
            title="Reap CFO Agent — ERP API",
            description=API_DESCRIPTION,
            version=API_VERSION,
            openapi_url="/openapi.json",
            docs_url=None,
            redoc_url=None,
        )
        self._setup_routes()

    def set_temporal_client(self, client: Optional[Client]) -> None:
        self._temporal_client = client

    def _setup_routes(self):
        @self.app.get(
            "/health",
            response_model=HealthResponse,
            tags=["Health"],
            summary="Service health",
            description="Liveness/readiness probe. Returns 503 when the database is unavailable.",
        )
        async def health_handler(response: Response):
            body = build_health_response(
                self.erp,
                temporal_connected=self._temporal_client is not None,
                version=API_VERSION,
            )
            if body.status == "unhealthy":
                response.status_code = 503
            return body

        @self.app.get("/docs", include_in_schema=False)
        async def scalar_docs():
            return get_scalar_api_reference(
                openapi_url=self.app.openapi_url,
                title=f"{self.app.title} — API Reference",
                theme=Theme.BLUE_PLANET,
                dark_mode=True,
                force_dark_mode_state="dark",
            )

        @self.app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def dashboard_handler(request: Request):
            return await self.get_dashboard(request)

        @self.app.get(
            "/api/coa/{tenant_id}",
            tags=["Chart of accounts"],
            summary="Get chart of accounts",
        )
        async def get_tenant_coa_handler(tenant_id: str):
            return await self.get_tenant_coa(tenant_id)

        @self.app.get(
            "/api/history/{tenant_id}",
            tags=["Tagging history"],
            summary="Get few-shot tagging history",
        )
        async def get_historical_context_handler(tenant_id: str):
            return await self.get_historical_context(tenant_id)

        @self.app.post(
            "/api/transactions",
            tags=["Transactions"],
            summary="Create transaction",
            description="Creates a ledger transaction and outbox entry; starts the tagging workflow.",
        )
        async def create_transaction_handler(req: TransactionRequest):
            return await self.create_transaction(req)

        @self.app.patch(
            "/api/transactions/{tx_id}",
            tags=["Transactions"],
            summary="Update transaction status",
        )
        async def update_ledger_status_handler(
            tx_id: str,
            status: str,
            account_code: Optional[str] = None,
            reasoning: Optional[str] = None,
        ):
            return await self.update_ledger_status(tx_id, status, account_code, reasoning)

        @self.app.post(
            "/api/transactions/{tx_id}/resolve",
            tags=["Transactions"],
            summary="Resolve human review",
            description="Signals the Temporal workflow with the accountant's chosen account code.",
        )
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
        history = self.erp.get_tagging_history(tenant_id)
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
