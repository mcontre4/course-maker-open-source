"""Users composition root: assemble use cases with operation-scoped adapters."""

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from redis import Redis
from sqlalchemy.orm import Session, sessionmaker

from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator
from app.shared.infrastructure.database import get_session
from app.shared.infrastructure.settings import Settings
from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator
from app.users.adapters.http.authentication import AuthHttpConfig
from app.users.adapters.http.router import get_create_user
from app.users.adapters.mysql.user_repository import MySqlUserRepository
from app.users.adapters.redis.authentication import RedisAuthLimiter
from app.users.application.authentication import AuthPolicy
from app.users.application.create_user import CreateUser
from app.users.ports.authentication import GoogleFlows, GoogleIdentityProvider, Passwords, Tokens
from app.users.ports.user_repository import UserRepository


def build_create_user(
    users: UserRepository,
    unit_of_work: UnitOfWork,
    id_generator: IdGenerator,
) -> CreateUser:
    """Assemble the create-user use case from its injected ports."""
    return CreateUser(users=users, unit_of_work=unit_of_work, id_generator=id_generator)


def install_dependencies(app: FastAPI) -> None:
    def create_user(session: Annotated[Session, Depends(get_session)]) -> CreateUser:
        return build_create_user(
            MySqlUserRepository(session), SqlAlchemyUnitOfWork(session), UuidIdGenerator()
        )

    app.dependency_overrides[get_create_user] = create_user


def install_authentication(app: FastAPI) -> None:
    """Wire one account repository and UoW to the same operation-scoped session."""
    from app.shared.infrastructure.system_clock import SystemClock
    from app.users.adapters.http import authentication as http
    from app.users.adapters.persistence.authentication import SqlAlchemyAccounts
    from app.users.adapters.persistence.user_repository import SqlAlchemyUserRepository
    from app.users.application import authentication as uc

    def services(session: Annotated[Session, Depends(get_session)]) -> http.AuthServices:
        runtime: AuthRuntime = app.state.auth
        dependencies = uc.AuthDependencies(
            SqlAlchemyAccounts(session),
            SqlAlchemyUserRepository(session),
            SqlAlchemyUnitOfWork(session),
            SystemClock(),
            UuidIdGenerator(),
            runtime.passwords,
            runtime.tokens,
            runtime.flows,
            runtime.google,
            runtime.policy,
        )
        return http.AuthServices(
            uc.SignUp(dependencies, dependencies.clock),
            uc.SignIn(dependencies, dependencies.clock),
            uc.GetSession(dependencies, dependencies.clock),
            uc.SignOut(dependencies, dependencies.clock),
            uc.RequestEmailAction(dependencies, dependencies.clock),
            uc.CompleteEmailAction(dependencies, dependencies.clock),
            uc.BeginGoogleSignIn(dependencies, dependencies.clock),
            uc.CompleteGoogleSignIn(dependencies, dependencies.clock),
        )

    app.dependency_overrides[http.get_auth_services] = services
    app.dependency_overrides[http.get_auth_config] = lambda: app.state.auth.http
    app.dependency_overrides[http.new_csrf_token] = lambda: app.state.auth.tokens.new()
    http.install_auth_error_handlers(app)


@dataclass(frozen=True)
class AuthRuntime:
    passwords: Passwords
    tokens: Tokens
    flows: GoogleFlows
    google: GoogleIdentityProvider
    policy: AuthPolicy
    http: AuthHttpConfig
    limiter: RedisAuthLimiter

    def rate(self, request: Request, category: str, email: str = "") -> None:
        ip = request.client.host if request.client else "unknown"
        # Ignore caller-supplied forwarded IP headers. Configure trusted proxies at the server.
        if not self.limiter.allow(f"ip:{category}:{ip}", 40):
            raise HTTPException(
                429, "Too many attempts. Try again later.", headers={"Retry-After": "900"}
            )
        if email and not self.limiter.allow(f"email:{category}:{email.strip().casefold()}", 10):
            raise HTTPException(
                429, "Too many attempts. Try again later.", headers={"Retry-After": "900"}
            )


def build_auth_runtime(
    config: Settings,
    redis: Redis,
    lifecycle: ExitStack,
    google_identity: GoogleIdentityProvider | None = None,
) -> AuthRuntime:
    import httpx
    from jwt import PyJWKClient

    from app.users.adapters.external.auth_security import ArgonPasswords, SecureTokens
    from app.users.adapters.external.google_identity import GoogleOpenId
    from app.users.adapters.redis.authentication import RedisGoogleFlows

    client = lifecycle.enter_context(httpx.Client(timeout=10, follow_redirects=False))
    public_url = config.auth_public_url
    return AuthRuntime(
        ArgonPasswords(),
        SecureTokens(),
        RedisGoogleFlows(redis),
        google_identity
        or GoogleOpenId(
            client,
            PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=10),
            config.google_client_id,
            config.google_client_secret.get_secret_value(),
            public_url + "/api/v1/auth/google/callback",
        ),
        AuthPolicy(
            public_url,
            config.auth_session_seconds,
            config.auth_idle_seconds,
            frozenset(
                (Path(__file__).parent / "adapters/external/password_blocklist/passwords.txt")
                .read_text()
                .splitlines()
            ),
        ),
        AuthHttpConfig(
            public_url,
            public_url.startswith("https://"),
            config.auth_session_seconds,
            bool(config.google_client_id),
        ),
        RedisAuthLimiter(redis),
    )


def start_account_mail(
    config: Settings,
    sessions: sessionmaker[Session],
    lifecycle: ExitStack,
) -> None:
    import smtplib
    import ssl
    from concurrent.futures import ThreadPoolExecutor
    from email.message import EmailMessage
    from threading import Event

    from app.shared.infrastructure.system_clock import SystemClock
    from app.users.adapters.external.mail_delivery import DeliverAccountMail
    from app.users.domain.authentication import AccountMail

    def send(mail: AccountMail) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = (
            config.mail_from,
            mail.recipient,
            mail.subject,
        )
        message["Message-ID"] = f"<{mail.id}@course-maker>"
        message.set_content(mail.body)
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
            if config.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password.get_secret_value())
            smtp.send_message(message)

    stop = Event()
    worker = lifecycle.enter_context(ThreadPoolExecutor(max_workers=1))
    worker.submit(DeliverAccountMail(sessions, SystemClock(), send).run, stop)
    lifecycle.callback(stop.set)
