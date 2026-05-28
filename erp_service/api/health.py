from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import text
from ..core.database import SqlAlchemyERP

HealthStatus = Literal["healthy", "degraded", "unhealthy"]


class HealthCheck(BaseModel):
    name: str
    status: Literal["ok", "degraded", "error"]
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: HealthStatus = Field(description="Aggregate service health")
    version: str = Field(description="API version")
    checks: List[HealthCheck]


def probe_database(session_factory) -> HealthCheck:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return HealthCheck(name="database", status="ok")
    except Exception as e:
        return HealthCheck(name="database", status="error", detail=str(e))


def probe_temporal(connected: bool) -> HealthCheck:
    if connected:
        return HealthCheck(name="temporal", status="ok")
    return HealthCheck(
        name="temporal",
        status="degraded",
        detail="Temporal client not connected (ingest works; workflows will not run)",
    )


def build_health_response(
    erp: SqlAlchemyERP,
    temporal_connected: bool,
    version: str = "0.1.0",
) -> HealthResponse:
    checks = [
        probe_database(erp.session_factory),
        probe_temporal(temporal_connected),
    ]
    if any(c.status == "error" for c in checks):
        aggregate: HealthStatus = "unhealthy"
    elif any(c.status == "degraded" for c in checks):
        aggregate = "degraded"
    else:
        aggregate = "healthy"
    return HealthResponse(status=aggregate, version=version, checks=checks)
