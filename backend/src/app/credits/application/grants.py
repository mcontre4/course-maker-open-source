from dataclasses import dataclass

from app.credits.domain.models import CreditTransaction, TransactionId
from app.credits.ports.repository import CreditsRepository
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class GrantCreditsRequest:
    owner_id: str
    credits: int
    reference: str
    description: str


@dataclass(frozen=True)
class GrantCreditsResponse:
    granted: bool
    balance: int


class GrantCredits:
    def __init__(
        self, repository: CreditsRepository, uow: UnitOfWork, clock: Clock, ids: IdGenerator
    ) -> None:
        self._repository, self._uow, self._clock, self._ids = repository, uow, clock, ids

    def execute(self, request: GrantCreditsRequest) -> GrantCreditsResponse:
        if (
            request.credits < 1
            or not request.reference
            or len(request.reference) > 100
            or not request.description
            or len(request.description) > 255
        ):
            raise ValueError("Invalid credit grant")
        with self._uow:
            account = self._repository.lock_account(request.owner_id)
            existing = self._repository.get_transaction(request.reference)
            if existing is not None:
                if (
                    existing.owner_id != request.owner_id
                    or existing.credits != request.credits
                    or existing.kind != "bonus"
                ):
                    raise ValueError("Grant reference already used for a different grant")
                return GrantCreditsResponse(False, account.credits)
            updated = account.change(request.credits)
            self._repository.save_account(updated)
            self._repository.add_transaction(
                CreditTransaction(
                    TransactionId.new(self._ids),
                    request.owner_id,
                    "bonus",
                    request.credits,
                    request.description,
                    self._clock.now().timestamp(),
                    request.reference,
                )
            )
            self._uow.commit()
        return GrantCreditsResponse(True, updated.credits)
