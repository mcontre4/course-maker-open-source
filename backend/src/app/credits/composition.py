from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import replace
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.credits.adapters import http
from app.credits.adapters.persistence import SqlAlchemyCredits
from app.credits.adapters.stripe import StripePayments
from app.credits.application import services as uc
from app.credits.application.grants import GrantCredits, GrantCreditsRequest
from app.credits.application.spending import RefundRequest, RefundUsage, SpendCredits, SpendRequest
from app.credits.ports.payments import Payments
from app.shared.application.credit_billing import (
    ChargeRequest,
    CreditBilling,
    MeteredOwnedUseCase,
    MeteredUseCase,
)
from app.shared.infrastructure.database import get_session
from app.shared.infrastructure.settings import DatabaseSettings, Settings
from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
from app.shared.infrastructure.system_clock import SystemClock
from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator


def build_payments(config: Settings, lifecycle: ExitStack) -> Payments:
    client = lifecycle.enter_context(httpx.Client(timeout=15))
    return StripePayments(
        client,
        config.stripe_secret_key.get_secret_value(),
        config.stripe_webhook_secret.get_secret_value(),
        config.auth_public_url,
        SystemClock(),
    )


class ScopedCreditBilling:
    """Each reservation/refund closes its transaction before lesson work starts."""

    def __init__(self, sessions: sessionmaker[Session], costs: dict[str, int]) -> None:
        self._sessions, self._costs = sessions, costs

    def charge(self, request: ChargeRequest) -> str:
        with self._sessions() as session:
            return (
                SpendCredits(
                    SqlAlchemyCredits(session),
                    SqlAlchemyUnitOfWork(session),
                    SystemClock(),
                    UuidIdGenerator(),
                )
                .execute(
                    SpendRequest(request.owner_id, request.action, self._costs[request.action])
                )
                .receipt
            )

    def refund(self, receipt: str) -> None:
        with self._sessions() as session:
            RefundUsage(
                SqlAlchemyCredits(session),
                SqlAlchemyUnitOfWork(session),
                SystemClock(),
                UuidIdGenerator(),
            ).execute(RefundRequest(receipt))


def credit_costs(config: Settings) -> dict[str, int]:
    return {
        "lesson_create": config.credit_create_cost,
        "lesson_generate": config.credit_generate_cost,
        "lesson_regenerate": config.credit_generate_cost,
        "lesson_media": config.credit_media_cost,
        "lesson_automatic": config.credit_automatic_cost,
        "course_generate": config.credit_generate_cost,
        "course_automatic": config.credit_automatic_cost,
        "interactive_generate": config.credit_generate_cost,
    }


def install_dependencies(app: FastAPI) -> None:
    def balance(session: Annotated[Session, Depends(get_session)]) -> uc.GetBalance:
        return uc.GetBalance(SqlAlchemyCredits(session))

    def transactions(session: Annotated[Session, Depends(get_session)]) -> uc.ListTransactions:
        return uc.ListTransactions(SqlAlchemyCredits(session))

    def create(session: Annotated[Session, Depends(get_session)]) -> uc.CreateCheckout:
        return uc.CreateCheckout(
            SqlAlchemyCredits(session),
            SqlAlchemyUnitOfWork(session),
            app.state.payments,
            UuidIdGenerator(),
            SystemClock(),
        )

    def checkout(session: Annotated[Session, Depends(get_session)]) -> uc.GetCheckout:
        return uc.GetCheckout(SqlAlchemyCredits(session), SystemClock())

    def webhook(session: Annotated[Session, Depends(get_session)]) -> uc.ProcessWebhook:
        return uc.ProcessWebhook(
            SqlAlchemyCredits(session),
            SqlAlchemyUnitOfWork(session),
            app.state.payments,
            UuidIdGenerator(),
            SystemClock(),
        )

    app.dependency_overrides.update(
        {
            http.get_balance: balance,
            http.get_transactions: transactions,
            http.get_create_checkout: create,
            http.get_checkout: checkout,
            http.get_webhook: webhook,
            http.get_costs: lambda: credit_costs(app.state.settings),
        }
    )
    http.install_error_handlers(app)


def install_metering(app: FastAPI, targets: dict[Callable[..., Any], str]) -> None:
    def wrap(factory: Callable[..., Any], action: str) -> Callable[..., Any]:
        def dependency(
            service: Annotated[Any, Depends(factory)],
            owner_id: Annotated[str, Depends(http.get_owner)],
        ) -> Any:
            billing: CreditBilling = app.state.credit_billing
            return MeteredUseCase(service.execute, billing, ChargeRequest(owner_id, action))

        return dependency

    for dependency, action in targets.items():
        factory = app.dependency_overrides.get(dependency, dependency)
        app.dependency_overrides[dependency] = wrap(factory, action)


def install_bundle_metering(
    app: FastAPI, dependency: Callable[..., Any], targets: dict[str, str]
) -> None:
    factory = app.dependency_overrides[dependency]

    def bundle(service: Annotated[Any, Depends(factory)]) -> Any:
        return replace(
            service,
            **{
                name: MeteredOwnedUseCase(
                    getattr(service, name).execute, app.state.credit_billing, action
                )
                for name, action in targets.items()
            },
        )

    app.dependency_overrides[dependency] = bundle


def grant_existing_user_credits(grant_id: str, credits: int, *, apply: bool) -> dict[str, object]:
    if (
        not grant_id
        or len(grant_id) > 50
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for c in grant_id
        )
        or credits < 1
    ):
        raise ValueError("Use a short alphanumeric batch ID and a positive credit amount")
    config = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_engine(config.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine)
    try:
        with engine.connect() as connection:
            # Snapshot the recipients before applying grants; do not include later signups.
            users = [
                str(row[0]) for row in connection.execute(text("SELECT id FROM users ORDER BY id"))
            ]
        results = []
        for owner_id in users:
            with sessions() as session:
                repository = SqlAlchemyCredits(session)
                if apply:
                    result = GrantCredits(
                        repository, SqlAlchemyUnitOfWork(session), SystemClock(), UuidIdGenerator()
                    ).execute(
                        GrantCreditsRequest(
                            owner_id,
                            credits,
                            f"grant:{grant_id}:{owner_id}",
                            f"Existing user credit grant ({grant_id})",
                        )
                    )
                    results.append(
                        {"userId": owner_id, "granted": result.granted, "balance": result.balance}
                    )
                else:
                    results.append(
                        {"userId": owner_id, "balance": repository.get_account(owner_id).credits}
                    )
        granted = sum(bool(row.get("granted")) for row in results)
        return {
            "grantId": grant_id,
            "applied": apply,
            "userCount": len(users),
            "grantedUsers": granted,
            "totalGranted": granted * credits,
            "users": results,
        }
    finally:
        engine.dispose()
