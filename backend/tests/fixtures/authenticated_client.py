"""Seed a real authenticated session for tests focused on other application features."""

from app.shared.infrastructure.system_clock import SystemClock
from app.users.adapters.persistence.authentication import SqlAlchemyAccounts
from app.users.adapters.persistence.user_repository import SqlAlchemyUserRepository
from app.users.domain.authentication import Account, LoginSession
from app.users.domain.user import User
from app.users.domain.user_id import UserId

TEST_ACCOUNT_ID = "user_00000000-0000-0000-0000-000000000001"


def authenticate_client(client, account_id=TEST_ACCOUNT_ID):
    """Create a funded feature-test account; production signup still starts at zero."""
    from app.credits.adapters.persistence import SqlAlchemyCredits
    from app.credits.domain.models import CreditTransaction, TransactionId
    from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator

    app = client.app
    runtime = app.state.auth
    identifier = UserId(account_id)
    token = runtime.tokens.new()
    now = SystemClock().now().timestamp()
    with app.state.resources.sessions.begin() as session:
        users, accounts = SqlAlchemyUserRepository(session), SqlAlchemyAccounts(session)
        if accounts.get_by_user_id(identifier) is None:
            user = User(identifier, f"{identifier}@example.com", "Runtime", "Learner")
            users.add(user)
            accounts.add(
                Account(
                    identifier,
                    user.email,
                    runtime.passwords.hash("a unique test passphrase 47!"),
                    verified=True,
                )
            )
        accounts.add_session(
            LoginSession(runtime.tokens.digest(token), identifier, now, now + 28800, now)
        )
        credits = SqlAlchemyCredits(session)
        reference = f"fixture:{account_id}"
        if credits.get_transaction(reference) is None:
            balance = credits.lock_account(account_id)
            credits.save_account(balance.change(10000))
            credits.add_transaction(
                CreditTransaction(
                    TransactionId.new(UuidIdGenerator()),
                    account_id,
                    "bonus",
                    10000,
                    "Feature test credit grant",
                    now,
                    reference,
                )
            )
    client.cookies.set(runtime.http.session_cookie, token)
    data = client.get("/api/v1/auth/session").json()
    assert data["user"] is not None, "Fixture session must authenticate before feature tests run"
    client.headers.update(
        {"Origin": app.state.settings.auth_public_url, "X-CSRF-Token": data["csrf_token"]}
    )
