"""FastAPI routes for the users domain.

Routes translate HTTP input into users application-service input. They must not
contain business logic.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.application.create_user import CreateUser, CreateUserRequest, CreateUserResponse
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.errors import UserError


class CreateUserHttpRequest(BaseModel):
    """Transport model — validated at the adapter boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class CreateUserHttpResponse(BaseModel):
    """Transport model — mapped from the application Response DTO."""

    id: str
    email: str
    first_name: str
    last_name: str


def _map_to_http(response: CreateUserResponse) -> CreateUserHttpResponse:
    return CreateUserHttpResponse(
        id=str(response.id),
        email=response.email,
        first_name=response.first_name,
        last_name=response.last_name,
    )


def get_create_user() -> CreateUser:
    raise RuntimeError("User services are not configured")


user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("", response_model=CreateUserHttpResponse, status_code=201)
def create_user(
    payload: CreateUserHttpRequest,
    use_case: CreateUser = Depends(get_create_user),
) -> CreateUserHttpResponse:
    """Translate HTTP input -> application Request DTO -> Response DTO -> HTTP."""
    try:
        response = use_case.execute(
            CreateUserRequest(
                email=str(payload.email),
                first_name=payload.first_name,
                last_name=payload.last_name,
            )
        )
    except UserError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmailAlreadyRegisteredError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _map_to_http(response)
