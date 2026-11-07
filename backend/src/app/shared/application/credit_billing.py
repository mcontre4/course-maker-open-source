from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.shared.domain.credits import InsufficientCredits  # noqa: F401


@dataclass(frozen=True)
class ChargeRequest:
    owner_id: str
    action: str


class CreditBilling(Protocol):
    def charge(self, request: ChargeRequest) -> str: ...

    def refund(self, receipt: str) -> None: ...


class MeteredUseCase[RequestT, ResponseT]:
    """Reserve before work; compensate synchronous failures in a separate transaction."""

    def __init__(
        self,
        execute: Callable[[RequestT], ResponseT],
        billing: CreditBilling,
        charge: ChargeRequest,
    ) -> None:
        self._execute, self._billing, self._charge = execute, billing, charge

    def execute(self, request: RequestT) -> ResponseT:
        receipt = self._billing.charge(self._charge)
        try:
            return self._execute(request)
        except BaseException:
            self._billing.refund(receipt)
            raise


class OwnedRequest(Protocol):
    @property
    def owner_id(self) -> str: ...


class MeteredOwnedUseCase[RequestT: OwnedRequest, ResponseT]:
    """For service bundles that also serve public, unmetered read operations."""

    def __init__(
        self, execute: Callable[[RequestT], ResponseT], billing: CreditBilling, action: str
    ) -> None:
        self._execute, self._billing, self._action = execute, billing, action

    def execute(self, request: RequestT) -> ResponseT:
        return MeteredUseCase(
            self._execute, self._billing, ChargeRequest(request.owner_id, self._action)
        ).execute(request)
