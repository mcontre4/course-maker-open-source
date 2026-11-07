"""Cookie/CSRF transport and authentication routes. No business rules live here."""

import hmac
import logging
from dataclasses import asdict, dataclass
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.users.application import authentication as uc
from app.users.application.auth_errors import (
    AccountConflictError,
    AuthenticationError,
    AuthenticationUnavailableError,
)
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.errors import UserError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuthHttpConfig:
    public_url: str
    secure: bool
    session_seconds: int
    google_enabled: bool

    @property
    def session_cookie(self) -> str:
        return "__Host-cm_session" if self.secure else "cm_session"

    @property
    def csrf_cookie(self) -> str:
        return "__Host-cm_csrf" if self.secure else "cm_csrf"

    @property
    def flow_cookie(self) -> str:
        return "__Host-cm_google" if self.secure else "cm_google"


@dataclass(frozen=True, slots=True)
class AuthServices:
    signup: uc.SignUp
    signin: uc.SignIn
    session: uc.GetSession
    signout: uc.SignOut
    email_action: uc.RequestEmailAction
    complete_action: uc.CompleteEmailAction
    begin_google: uc.BeginGoogleSignIn
    complete_google: uc.CompleteGoogleSignIn


def get_auth_services() -> AuthServices:
    raise RuntimeError("Authentication is not configured")


def get_auth_config() -> AuthHttpConfig:
    raise RuntimeError("Authentication is not configured")


def new_csrf_token() -> str:
    raise RuntimeError("CSRF generator is not configured")


Services = Annotated[AuthServices, Depends(get_auth_services)]
Config = Annotated[AuthHttpConfig, Depends(get_auth_config)]


def _cookie(
    response: Response, name: str, value: str, config: AuthHttpConfig, max_age: int
) -> None:
    response.set_cookie(
        name, value, max_age=max_age, secure=config.secure, httponly=True, samesite="lax", path="/"
    )


def check_csrf(request: Request, config: Config) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin", "")
    expected = urlsplit(config.public_url)
    if origin != f"{expected.scheme}://{expected.netloc}":
        raise HTTPException(403, "Request origin rejected")
    cookie = request.cookies.get(config.csrf_cookie, "")
    header = request.headers.get("x-csrf-token", "")
    if (
        not cookie
        or not header
        or len(header) > 128
        or not hmac.compare_digest(
            cookie.encode(),
            header.encode(),
        )
    ):
        raise HTTPException(403, "Reload the page and try again")


def require_account(request: Request, services: Services, config: Config) -> uc.ProfileResponse:
    token = request.cookies.get(config.session_cookie, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "Please sign in")
    profile = services.session.execute(uc.SessionRequest(token))
    check_csrf(request, config)
    return profile


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class SignInInput(EmailInput):
    password: SecretStr = Field(min_length=1, max_length=128)


class SignUpInput(EmailInput):
    password: SecretStr = Field(min_length=15, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=32, max_length=128)


class ResetInput(ActionInput):
    password: SecretStr = Field(min_length=15, max_length=128)


router = APIRouter(
    prefix="/api/v1/auth", tags=["authentication"], dependencies=[Depends(check_csrf)]
)


@router.get("/session")
def session(
    request: Request,
    response: Response,
    services: Services,
    config: Config,
    csrf: Annotated[str, Depends(new_csrf_token)],
) -> dict[str, object]:
    token = request.cookies.get(config.csrf_cookie, "")
    if not token or len(token) > 128:
        token = csrf
        _cookie(response, config.csrf_cookie, token, config, config.session_seconds)
    user = None
    try:
        raw = request.cookies.get(config.session_cookie, "")
        if raw and len(raw) <= 128:
            user = asdict(services.session.execute(uc.SessionRequest(raw)))
    except AuthenticationError:
        # A late response for a revoked session must not erase a newer sign-in cookie.
        pass
    return {"user": user, "csrf_token": token, "google_enabled": config.google_enabled}


@router.post("/signup", status_code=202)
def signup(
    body: SignUpInput,
    request: Request,
    services: Services,
) -> dict[str, str]:
    request.app.state.auth.rate(request, "signup", str(body.email))
    result = services.signup.execute(
        uc.SignUpRequest(
            str(body.email),
            body.password.get_secret_value(),
            body.first_name,
            body.last_name,
        )
    )
    return asdict(result)


def _signed_in(
    response: Response, result: uc.SignInResponse, config: AuthHttpConfig, csrf: str
) -> dict[str, object]:
    logger.info("Account sign-in succeeded", extra={"account_id": result.user.id})
    _cookie(response, config.session_cookie, result.session_token, config, config.session_seconds)
    _cookie(response, config.csrf_cookie, csrf, config, config.session_seconds)
    return {
        "user": asdict(result.user),
        "csrf_token": csrf,
        "google_enabled": config.google_enabled,
    }


@router.post("/signin")
def signin(
    body: SignInInput,
    request: Request,
    response: Response,
    services: Services,
    config: Config,
    csrf: Annotated[str, Depends(new_csrf_token)],
) -> dict[str, object]:
    request.app.state.auth.rate(request, "signin", str(body.email))
    result = services.signin.execute(
        uc.SignInRequest(
            str(body.email),
            body.password.get_secret_value(),
            request.cookies.get(config.session_cookie, ""),
        )
    )
    return _signed_in(response, result, config, csrf)


@router.post("/signout", status_code=204)
def signout(request: Request, services: Services, config: Config) -> Response:
    services.signout.execute(uc.SessionRequest(request.cookies.get(config.session_cookie, "")))
    logger.info("Account signed out")
    response = Response(status_code=204)
    for name in (config.session_cookie, config.csrf_cookie, config.flow_cookie):
        response.delete_cookie(name, path="/", secure=config.secure, httponly=True, samesite="lax")
    return response


@router.post("/forgot-password", status_code=202)
def forgot_password(body: EmailInput, request: Request, services: Services) -> dict[str, str]:
    request.app.state.auth.rate(request, "email", str(body.email))
    return asdict(services.email_action.execute(uc.EmailActionRequest(str(body.email), "reset")))


@router.post("/resend-verification", status_code=202)
def resend_verification(body: EmailInput, request: Request, services: Services) -> dict[str, str]:
    request.app.state.auth.rate(request, "email", str(body.email))
    return asdict(services.email_action.execute(uc.EmailActionRequest(str(body.email), "verify")))


@router.post("/verify-email")
def verify_email(body: ActionInput, request: Request, services: Services) -> dict[str, str]:
    request.app.state.auth.rate(request, "action")
    return asdict(
        services.complete_action.execute(
            uc.CompleteActionRequest(
                body.token.get_secret_value(),
                "verify",
            )
        )
    )


@router.post("/reset-password")
def reset_password(body: ResetInput, request: Request, services: Services) -> dict[str, str]:
    request.app.state.auth.rate(request, "action")
    return asdict(
        services.complete_action.execute(
            uc.CompleteActionRequest(
                body.token.get_secret_value(),
                "reset",
                body.password.get_secret_value(),
            )
        )
    )


@router.post("/google/start")
def google_start(
    request: Request, response: Response, services: Services, config: Config
) -> dict[str, str]:
    request.app.state.auth.rate(request, "google")
    result = services.begin_google.execute(uc.BeginGoogleRequest())
    _cookie(response, config.flow_cookie, result.state, config, 600)
    return {"url": result.url}


@router.get("/google/callback")
def google_callback(
    request: Request,
    services: Services,
    config: Config,
    csrf: Annotated[str, Depends(new_csrf_token)],
) -> RedirectResponse:
    response = RedirectResponse(config.public_url + "/login?error=google", status_code=303)
    state, code = request.query_params.get("state", ""), request.query_params.get("code", "")
    expected = request.cookies.get(config.flow_cookie, "")
    try:
        if (
            not code
            or len(code) > 4096
            or not state
            or len(state) > 128
            or not expected
            or not hmac.compare_digest(state.encode(), expected.encode())
            or "error" in request.query_params
        ):
            raise AuthenticationError()
        result = services.complete_google.execute(
            uc.CompleteGoogleRequest(
                state,
                code,
                request.cookies.get(config.session_cookie, ""),
            )
        )
        response = RedirectResponse(config.public_url + "/", status_code=303)
        _signed_in(response, result, config, csrf)
    except AccountConflictError:
        response = RedirectResponse(
            config.public_url + "/login?error=account_exists", status_code=303
        )
    except (AuthenticationError, AuthenticationUnavailableError, EmailAlreadyRegisteredError):
        pass
    response.delete_cookie(config.flow_cookie, path="/", secure=config.secure, httponly=True)
    return response


def install_auth_error_handlers(app: FastAPI) -> None:
    async def authentication_error(request: Request, exc: Exception) -> JSONResponse:
        logger.warning("Authentication rejected", extra={"path": request.url.path})
        return JSONResponse(
            {
                "detail": "Unable to sign in. Check your credentials and verify your email."
                if request.url.path.endswith("signin")
                else "This session or link is invalid or has expired."
            },
            status_code=401,
        )

    async def unavailable(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            {"detail": "Sign-in is temporarily unavailable. Please try again."}, status_code=503
        )

    async def invalid_user(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    async def validation(request: Request, exc: Exception) -> JSONResponse:
        # FastAPI's default validation response includes the original password/token input.
        assert isinstance(exc, RequestValidationError)
        return JSONResponse(
            {
                "detail": [
                    {"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()
                ]
            },
            status_code=422,
        )

    app.add_exception_handler(AuthenticationError, authentication_error)
    app.add_exception_handler(AuthenticationUnavailableError, unavailable)
    app.add_exception_handler(UserError, invalid_user)
    app.add_exception_handler(RequestValidationError, validation)
