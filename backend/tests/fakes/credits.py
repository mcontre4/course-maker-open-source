from dataclasses import replace

from app.credits.domain.models import CreditAccount, PaymentSession


class InMemoryCredits:
    def __init__(self):
        self.accounts = {}
        self.transactions = {}
        self.checkouts = {}

    def get_account(self, owner_id):
        return self.accounts.get(owner_id, CreditAccount(owner_id))

    def lock_account(self, owner_id):
        return self.get_account(owner_id)

    def save_account(self, account):
        self.accounts[account.owner_id] = account

    def add_transaction(self, transaction):
        assert transaction.reference not in self.transactions
        self.transactions[transaction.reference] = transaction

    def get_transaction(self, reference):
        return self.transactions.get(reference)

    def list_transactions(self, owner_id, limit, before):
        rows = sorted(
            (t for t in self.transactions.values() if t.owner_id == owner_id),
            key=lambda t: (t.created_at, str(t.id)),
            reverse=True,
        )
        return tuple(t for t in rows if before is None or (t.created_at, str(t.id)) < before)[
            :limit
        ]

    def add_checkout(self, checkout):
        self.checkouts[str(checkout.id)] = checkout

    def get_checkout(self, checkout_id, *, lock=False):
        return self.checkouts.get(checkout_id)

    def save_checkout(self, checkout):
        self.checkouts[str(checkout.id)] = replace(checkout)


class ScriptedPayments:
    def __init__(self):
        self.event = None
        self.calls = []
        self.error = None
        self.on_create = None

    def create_session(self, checkout, pack):
        self.calls.append((checkout, pack))
        if self.error:
            raise self.error
        if self.on_create:
            self.on_create(checkout)
        return PaymentSession("cs_test_1", "https://checkout.stripe.com/test", 1900000000)

    def verify_event(self, payload, signature):
        return self.event


class RecordingCreditBilling:
    def __init__(self):
        self.charges = []
        self.refunds = []
        self.error = None

    def charge(self, request):
        if self.error:
            raise self.error
        self.charges.append(request)
        return "receipt"

    def refund(self, receipt):
        self.refunds.append(receipt)
