from secrets import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException, Request, Response


def require_internal_access(
    request: Request,
    response: Response,
    key: Annotated[str, Header(alias="X-Internal-Tools-Key")] = "",
) -> None:
    secret = getattr(request.app.state.settings, "internal_tools_key", None)
    configured = secret.get_secret_value() if secret else ""
    headers = {"Cache-Control": "no-store"}
    if not configured:
        raise HTTPException(404, "Internal tools are disabled", headers=headers)
    if not compare_digest(key.encode(), configured.encode()):
        raise HTTPException(403, "Internal access required", headers=headers)
    response.headers.update(headers)
