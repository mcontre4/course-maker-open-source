from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.credits.application import services as uc
from app.credits.ports.payments import InvalidPaymentEvent, PaymentsUnavailable
from app.shared.domain.credits import InsufficientCredits


class View(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class BalanceView(View):
    credits: int


class PackView(View):
    id: str
    name: str
    credits: int
    bonus_credits: int
    price_cents: int
    currency: str
    badge: str | None


class PacksView(View):
    packs: list[PackView]


class TransactionView(View):
    id: str
    kind: str
    credits: int
    description: str
    created_at: str


class TransactionsView(View):
    items: list[TransactionView]
    next_cursor: str | None


class CheckoutInput(View):
    pack_id: str = Field(min_length=1, max_length=50)


class CheckoutView(View):
    checkout_id: str
    url: str


class CheckoutStatusView(View):
    status: str
    credits_added: int


def get_owner() -> str:
    raise RuntimeError("Credit account authentication is not configured")


def get_balance() -> uc.GetBalance:
    raise RuntimeError("Credits are not configured")


def get_transactions() -> uc.ListTransactions:
    raise RuntimeError("Credits are not configured")


def get_create_checkout() -> uc.CreateCheckout:
    raise RuntimeError("Credits are not configured")


def get_checkout() -> uc.GetCheckout:
    raise RuntimeError("Credits are not configured")


def get_webhook() -> uc.ProcessWebhook:
    raise RuntimeError("Credits are not configured")


def get_costs() -> dict[str, int]:
    raise RuntimeError("Credit costs are not configured")


router = APIRouter(prefix="/api/v1/credits", tags=["credits"])
Owner = Annotated[str, Depends(get_owner)]


@router.get("", response_model=BalanceView)
def balance(owner: Owner, service: Annotated[uc.GetBalance, Depends(get_balance)]) -> BalanceView:
    return BalanceView.model_validate(service.execute(uc.BalanceRequest(owner)))


@router.get("/packs", response_model=PacksView)
def packs(owner: Owner) -> PacksView:
    return PacksView.model_validate(uc.ListPacks().execute(uc.PacksRequest()))


@router.get("/policy")
def policy(owner: Owner, costs: Annotated[dict[str, int], Depends(get_costs)]) -> dict[str, object]:
    return {"costs": costs, "creditsExpire": False, "lowCreditThreshold": 25}


@router.get("/transactions", response_model=TransactionsView)
def transactions(
    owner: Owner,
    service: Annotated[uc.ListTransactions, Depends(get_transactions)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> TransactionsView:
    result = service.execute(uc.TransactionsRequest(owner, limit, cursor))
    return TransactionsView(
        items=[
            TransactionView(
                id=t.id,
                kind=t.kind,
                credits=t.credits,
                description=t.description,
                created_at=datetime.fromtimestamp(t.created_at, UTC).isoformat(),
            )
            for t in result.items
        ],
        next_cursor=result.next_cursor,
    )


@router.post("/checkout", response_model=CheckoutView)
def create_checkout(
    payload: CheckoutInput,
    owner: Owner,
    service: Annotated[uc.CreateCheckout, Depends(get_create_checkout)],
) -> CheckoutView:
    return CheckoutView.model_validate(
        service.execute(uc.CreateCheckoutRequest(owner, payload.pack_id))
    )


@router.get("/checkout/{checkout_id}", response_model=CheckoutStatusView)
def checkout(
    checkout_id: str, owner: Owner, service: Annotated[uc.GetCheckout, Depends(get_checkout)]
) -> CheckoutStatusView:
    return CheckoutStatusView.model_validate(
        service.execute(uc.CheckoutRequest(owner, checkout_id))
    )


@router.post("/webhook")
async def webhook(
    request: Request, service: Annotated[uc.ProcessWebhook, Depends(get_webhook)]
) -> dict[str, bool]:
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 1_048_576:
            raise HTTPException(413, "Webhook body too large")
    # Stripe authenticates with a signature, independently of browser session/CSRF cookies.
    from starlette.concurrency import run_in_threadpool

    result = await run_in_threadpool(
        service.execute,
        uc.WebhookRequest(bytes(payload), request.headers.get("stripe-signature", "")),
    )
    return {"received": result.received}


def install_error_handlers(app: FastAPI) -> None:
    async def handle(request: Request, error: Exception) -> JSONResponse:
        status = 400
        if isinstance(error, InsufficientCredits):
            status = 402
        elif isinstance(error, uc.CreditsNotFound):
            status = 404
        elif isinstance(error, PaymentsUnavailable):
            status = 503
        return JSONResponse({"detail": str(error)}, status_code=status)

    for error in (
        uc.CreditsNotFound,
        uc.InvalidCreditsRequest,
        InvalidPaymentEvent,
        PaymentsUnavailable,
        InsufficientCredits,
    ):
        app.add_exception_handler(error, handle)
