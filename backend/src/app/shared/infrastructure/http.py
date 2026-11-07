from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.shared.application.get_readiness import GetReadiness, ReadinessRequest
from app.shared.domain.errors import InvalidIdentifierError

bearer = HTTPBearer(auto_error=False)
health_router = APIRouter(prefix="/health", tags=["health"])


def authorize(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> None:
    expected = request.app.state.settings.api_key.get_secret_value()
    if credentials is None or not compare_digest(
        credentials.credentials.encode(), expected.encode()
    ):
        raise HTTPException(401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})


def get_readiness() -> GetReadiness:
    raise RuntimeError("Readiness service is not configured")


@health_router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/ready", dependencies=[Depends(authorize)])
def ready(service: Annotated[GetReadiness, Depends(get_readiness)]) -> JSONResponse:
    status = service.execute(ReadinessRequest())
    return JSONResponse(
        status_code=200 if status.database else 503,
        content={
            "database": status.database,
            "cache": status.cache,
            "storageConfigured": status.storage_configured,
        },
    )


async def invalid_identifier(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def register_http_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InvalidIdentifierError, invalid_identifier)
