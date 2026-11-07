"""One interactor per authentication use case; all volatile details are injected."""

from dataclasses import dataclass, field

from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock
from app.shared.domain.id_generator import IdGenerator
from app.users.application.auth_errors import AccountConflictError, AuthenticationError
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.authentication import (
    Account,
    AccountAction,
    AccountMail,
    LoginSession,
    normalize_email,
    validate_password,
)
from app.users.domain.user import User
from app.users.domain.user_id import UserId
from app.users.ports.authentication import (
    Accounts,
    GoogleFlow,
    GoogleFlows,
    GoogleIdentityProvider,
    Passwords,
    Tokens,
)
from app.users.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class AuthPolicy:
    public_url: str
    session_seconds: int = 28800
    idle_seconds: int = 1800
    common_passwords: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class AuthDependencies:
    accounts: Accounts
    users: UserRepository
    uow: UnitOfWork
    clock: Clock
    ids: IdGenerator
    passwords: Passwords
    tokens: Tokens
    flows: GoogleFlows
    google: GoogleIdentityProvider
    policy: AuthPolicy


@dataclass(frozen=True, slots=True)
class ProfileResponse:
    id: str
    email: str
    first_name: str
    last_name: str
    verified: bool


@dataclass(frozen=True, slots=True)
class SignInResponse:
    user: ProfileResponse
    session_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class MessageResponse:
    message: str = "If this address can be used, you’ll receive an email with the next steps."


@dataclass(frozen=True, slots=True)
class SignUpRequest:
    email: str
    password: str = field(repr=False)
    first_name: str = ""
    last_name: str = ""


@dataclass(frozen=True, slots=True)
class SignInRequest:
    email: str
    password: str = field(repr=False)
    previous_token: str = field(default="", repr=False)


@dataclass(frozen=True, slots=True)
class SessionRequest:
    token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class EmailActionRequest:
    email: str
    purpose: str


@dataclass(frozen=True, slots=True)
class CompleteActionRequest:
    token: str = field(repr=False)
    purpose: str = "verify"
    password: str = field(default="", repr=False)


@dataclass(frozen=True, slots=True)
class BeginGoogleRequest:
    pass


@dataclass(frozen=True, slots=True)
class BeginGoogleResponse:
    url: str
    state: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CompleteGoogleRequest:
    state: str = field(repr=False)
    code: str = field(repr=False)
    previous_token: str = field(default="", repr=False)


class _AuthUseCase:
    def __init__(self, dependencies: AuthDependencies, clock: Clock) -> None:
        self._d = dependencies
        self._clock = clock

    def _profile(self, account: Account) -> ProfileResponse:
        user = self._d.users.get_by_id(account.user_id)
        if user is None:
            raise AuthenticationError()
        return ProfileResponse(
            str(user.id), user.email, user.first_name, user.last_name, account.verified
        )

    def _mail_action(self, account: Account, purpose: str) -> None:
        now = self._clock.now().timestamp()
        token = self._d.tokens.new()
        expires = now + (1800 if purpose == "reset" else 86400)
        self._d.accounts.delete_actions(account.user_id, purpose)
        self._d.accounts.add_action(
            AccountAction(
                self._d.tokens.digest(token),
                account.user_id,
                purpose,
                expires,
            )
        )
        route = "reset-password" if purpose == "reset" else "verify-email"
        url = f"{self._d.policy.public_url}/{route}#token={token}"
        subject = "Reset your password" if purpose == "reset" else "Verify your email"
        self._d.accounts.enqueue_mail(
            AccountMail(
                "mail_" + str(self._d.ids.new_uuid()),
                account.email,
                subject,
                f"{subject} for Course Maker:\n\n{url}\n\n"
                "If you didn’t request this, ignore this email.",
                expires,
            )
        )

    def _sign_in(self, account: Account, previous: str) -> SignInResponse:
        token = self._d.tokens.new()
        now = self._clock.now().timestamp()
        self._d.accounts.delete_session(self._d.tokens.digest(previous))
        self._d.accounts.add_session(
            LoginSession(
                self._d.tokens.digest(token),
                account.user_id,
                now,
                now + self._d.policy.session_seconds,
                now,
            )
        )
        return SignInResponse(self._profile(account), token)


class SignUp(_AuthUseCase):
    def execute(self, request: SignUpRequest) -> MessageResponse:
        validate_password(request.password, self._d.policy.common_passwords)
        # Hash before any lookup to keep duplicate registration similarly expensive.
        encoded = self._d.passwords.hash(request.password)
        email = normalize_email(request.email)
        try:
            with self._d.uow:
                if self._d.users.get_by_email(email) is not None:
                    return MessageResponse()
                user = User(
                    UserId("user_" + str(self._d.ids.new_uuid())),
                    email,
                    request.first_name.strip(),
                    request.last_name.strip(),
                )
                account = Account(user.id, email, encoded)
                self._d.users.add(user)
                self._d.accounts.add(account)
                self._mail_action(account, "verify")
                self._d.uow.commit()
        except EmailAlreadyRegisteredError:
            # The unique constraint also protects concurrent registrations.
            pass
        return MessageResponse()


class SignIn(_AuthUseCase):
    def execute(self, request: SignInRequest) -> SignInResponse:
        # End the read transaction before expensive password verification.
        with self._d.uow:
            account = self._d.accounts.get_by_email(normalize_email(request.email))
        valid = self._d.passwords.verify(
            request.password,
            account.password_hash if account else None,
        )
        if not valid or account is None or not account.verified:
            raise AuthenticationError()
        with self._d.uow:
            # Recheck under the account lock: reset must not race a stale password login.
            current = self._d.accounts.get_by_user_id(account.user_id)
            if current != account:
                raise AuthenticationError()
            response = self._sign_in(account, request.previous_token)
            self._d.uow.commit()
            return response


class GetSession(_AuthUseCase):
    def execute(self, request: SessionRequest) -> ProfileResponse:
        with self._d.uow:
            session = self._d.accounts.get_session(self._d.tokens.digest(request.token))
            now = self._clock.now().timestamp()
            if session is None or not session.active(now, self._d.policy.idle_seconds):
                raise AuthenticationError()
            account = self._d.accounts.get_by_user_id(session.user_id)
            if account is None or not account.verified:
                raise AuthenticationError()
            session = self._d.accounts.get_session_for_authentication(
                self._d.tokens.digest(request.token)
            )
            if session is None or not session.active(now, self._d.policy.idle_seconds):
                raise AuthenticationError()
            result = self._profile(account)
            self._d.accounts.save_session(session.touch(now))
            self._d.uow.commit()
            return result


class SignOut(_AuthUseCase):
    def execute(self, request: SessionRequest) -> MessageResponse:
        with self._d.uow:
            self._d.accounts.delete_session(self._d.tokens.digest(request.token))
            self._d.uow.commit()
        return MessageResponse("Signed out")


class RequestEmailAction(_AuthUseCase):
    def execute(self, request: EmailActionRequest) -> MessageResponse:
        if request.purpose not in {"verify", "reset"}:
            raise AuthenticationError()
        with self._d.uow:
            account = self._d.accounts.get_by_email(normalize_email(request.email))
            if (
                account
                and account.password_hash
                and (request.purpose == "reset" or not account.verified)
            ):
                # Serialize resends and password resets on the same account.
                account = self._d.accounts.get_by_user_id(account.user_id)
                if account is None:
                    raise AuthenticationError()
                self._mail_action(account, request.purpose)
                self._d.uow.commit()
        return MessageResponse()


class CompleteEmailAction(_AuthUseCase):
    def execute(self, request: CompleteActionRequest) -> MessageResponse:
        if request.purpose not in {"verify", "reset"}:
            raise AuthenticationError()
        encoded = None
        if request.purpose == "reset":
            validate_password(request.password, self._d.policy.common_passwords)
            encoded = self._d.passwords.hash(request.password)
        with self._d.uow:
            action = self._d.accounts.consume_action(
                self._d.tokens.digest(request.token),
                request.purpose,
                self._clock.now().timestamp(),
            )
            if action is None:
                raise AuthenticationError()
            account = self._d.accounts.get_by_user_id(action.user_id)
            if account is None:
                raise AuthenticationError()
            self._d.accounts.save(account.reset_password(encoded) if encoded else account.verify())
            if encoded:
                self._d.accounts.revoke_sessions(account.user_id)
            self._d.accounts.delete_actions(account.user_id, request.purpose)
            self._d.uow.commit()
        return MessageResponse(
            "Password updated. Please sign in."
            if encoded
            else "Email verified. You can now sign in."
        )


class BeginGoogleSignIn(_AuthUseCase):
    def execute(self, request: BeginGoogleRequest) -> BeginGoogleResponse:
        state = self._d.tokens.new()
        flow = GoogleFlow(self._d.tokens.new(), self._d.tokens.new())
        url = self._d.google.authorization_url(state, flow)
        self._d.flows.put(state, flow)
        return BeginGoogleResponse(url, state)


class CompleteGoogleSignIn(_AuthUseCase):
    def execute(self, request: CompleteGoogleRequest) -> SignInResponse:
        flow = self._d.flows.consume(request.state)
        if flow is None:
            raise AuthenticationError()
        # All provider I/O completes before entering the database transaction.
        identity = self._d.google.exchange(request.code, flow)
        with self._d.uow:
            account = self._d.accounts.get_by_google_subject(identity.subject)
            if account is None:
                email = normalize_email(identity.email)
                if self._d.users.get_by_email(email) is not None:
                    raise AccountConflictError()
                user = User(
                    UserId("user_" + str(self._d.ids.new_uuid())),
                    email,
                    identity.first_name or "Google",
                    identity.last_name or "User",
                )
                self._d.users.add(user)
                account = Account(user.id, email, google_subject=identity.subject, verified=True)
                self._d.accounts.add(account)
            response = self._sign_in(account, request.previous_token)
            self._d.uow.commit()
            return response
