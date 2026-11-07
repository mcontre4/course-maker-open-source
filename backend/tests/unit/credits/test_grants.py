import pytest

from app.credits.application.grants import GrantCredits, GrantCreditsRequest
from app.credits.domain.models import CreditAccount, CreditTransaction, TransactionId

OWNER = "user_00000000-0000-0000-0000-000000000001"
REFERENCE = "grant:existing-users:owner"


def test_grants_add_to_existing_balance_once_and_record_bonus(repository, uow, clock, ids):
    repository.save_account(CreditAccount(OWNER, 17))
    service = GrantCredits(repository, uow, clock, ids)
    request = GrantCreditsRequest(OWNER, 1_000_000, REFERENCE, "Existing user grant")
    result = service.execute(request)
    assert result.granted and result.balance == 1_000_017
    assert repository.get_account(OWNER).credits == 1_000_017
    transaction = repository.get_transaction(REFERENCE)
    assert transaction.kind == "bonus" and transaction.credits == 1_000_000
    assert not service.execute(request).granted
    assert repository.get_account(OWNER).credits == 1_000_017
    assert len(repository.transactions) == 1


@pytest.mark.parametrize("owner,credits", [(OWNER, 2_000_000), ("other", 1_000_000)])
def test_reference_cannot_be_reused_for_a_different_grant(
    repository,
    uow,
    clock,
    ids,
    owner,
    credits,
):
    service = GrantCredits(repository, uow, clock, ids)
    service.execute(GrantCreditsRequest(OWNER, 1_000_000, REFERENCE, "Existing user grant"))
    with pytest.raises(ValueError, match="different grant"):
        service.execute(GrantCreditsRequest(owner, credits, REFERENCE, "Conflicting grant"))
    assert repository.get_account(OWNER).credits == 1_000_000


@pytest.mark.parametrize(
    "credits,reference,description",
    [
        (0, REFERENCE, "Grant"),
        (-1, REFERENCE, "Grant"),
        (1, "", "Grant"),
        (1, "x" * 101, "Grant"),
        (1, REFERENCE, ""),
        (1, REFERENCE, "x" * 256),
    ],
)
def test_invalid_grants_never_change_balances(
    repository,
    uow,
    clock,
    ids,
    credits,
    reference,
    description,
):
    with pytest.raises(ValueError):
        GrantCredits(repository, uow, clock, ids).execute(
            GrantCreditsRequest(OWNER, credits, reference, description)
        )
    assert not repository.transactions and repository.get_account(OWNER).credits == 0


@pytest.mark.parametrize(
    "kind,credits",
    [
        ("purchase", -1),
        ("refund", -1),
        ("bonus", -1),
        ("usage", 1),
        ("unknown", 1),
    ],
)
def test_ledger_enforces_transaction_directions(ids, kind, credits):
    with pytest.raises(ValueError):
        CreditTransaction(TransactionId.new(ids), OWNER, kind, credits, "Invalid", 0, "bad")
