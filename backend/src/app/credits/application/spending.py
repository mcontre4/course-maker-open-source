from dataclasses import dataclass

from app.credits.domain.models import CreditTransaction, TransactionId
from app.credits.ports.repository import CreditsRepository
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class SpendRequest:
    owner_id: str
    action: str
    cost: int


@dataclass(frozen=True)
class SpendResponse:
    receipt: str


class SpendCredits:
    def __init__(
        self, repository: CreditsRepository, uow: UnitOfWork, clock: Clock, ids: IdGenerator
    ) -> None:
        self._repository, self._uow, self._clock, self._ids = repository, uow, clock, ids

    def execute(self, request: SpendRequest) -> SpendResponse:
        if request.cost < 1:
            raise ValueError("Credit cost must be positive")
        receipt = str(TransactionId.new(self._ids))
        with self._uow:
            account = self._repository.lock_account(request.owner_id)
            self._repository.save_account(account.change(-request.cost))
            self._repository.add_transaction(
                CreditTransaction(
                    TransactionId(receipt),
                    request.owner_id,
                    "usage",
                    -request.cost,
                    request.action.replace("_", " ").capitalize(),
                    self._clock.now().timestamp(),
                    receipt,
                )
            )
            self._uow.commit()
        return SpendResponse(receipt)


@dataclass(frozen=True)
class RefundRequest:
    receipt: str


@dataclass(frozen=True)
class RefundResponse:
    refunded: bool


class RefundUsage:
    def __init__(
        self, repository: CreditsRepository, uow: UnitOfWork, clock: Clock, ids: IdGenerator
    ) -> None:
        self._repository, self._uow, self._clock, self._ids = repository, uow, clock, ids

    def execute(self, request: RefundRequest) -> RefundResponse:
        with self._uow:
            usage = self._repository.get_transaction(request.receipt)
            if usage is None or usage.kind != "usage":
                return RefundResponse(False)
            account = self._repository.lock_account(usage.owner_id)
            reference = f"refund:{request.receipt}"
            if self._repository.get_transaction(reference) is not None:
                return RefundResponse(False)
            self._repository.save_account(account.change(-usage.credits))
            self._repository.add_transaction(
                CreditTransaction(
                    TransactionId.new(self._ids),
                    usage.owner_id,
                    "refund",
                    -usage.credits,
                    f"Failed operation: {usage.description}",
                    self._clock.now().timestamp(),
                    reference,
                )
            )
            self._uow.commit()
        return RefundResponse(True)
