import threading
import uvicorn
from loguru import logger
from erp_service.api.router import AccountingGatewayRouter
from erp_service.core.database import SqlAlchemyERP
from bootstrap.config import ERP_HOST, ERP_PORT

def create_router(erp: SqlAlchemyERP) -> AccountingGatewayRouter:
    """
    Creates and configures the AccountingGatewayRouter FastAPI application.
    """
    return AccountingGatewayRouter(erp)

def run_dashboard(router: AccountingGatewayRouter, host: str = ERP_HOST, port: int = ERP_PORT):
    """
    Blocks while running the uvicorn API/dashboard server.
    """
    logger.info(f"Starting ERP Service on http://{host}:{port}")
    uvicorn.run(router.app, host=host, port=port, log_level="warning")

def start_dashboard_thread(router: AccountingGatewayRouter, host: str = ERP_HOST, port: int = ERP_PORT) -> threading.Thread:
    """
    Starts the uvicorn API/dashboard server inside a daemon background thread.
    """
    thread = threading.Thread(target=run_dashboard, args=(router, host, port), daemon=True)
    thread.start()
    return thread
