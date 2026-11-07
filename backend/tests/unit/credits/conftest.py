import pytest
from fakes.authentication import MutableAuthClock
from fakes.courses import SequenceIds
from fakes.credits import InMemoryCredits, ScriptedPayments
from fakes.shared.application.unit_of_work import FakeUnitOfWork

from app.credits.application.services import CreateCheckout, ProcessWebhook


@pytest.fixture
def repository():
    return InMemoryCredits()


@pytest.fixture
def clock():
    return MutableAuthClock()


@pytest.fixture
def ids():
    return SequenceIds()


@pytest.fixture
def uow():
    return FakeUnitOfWork()


@pytest.fixture
def payments():
    return ScriptedPayments()


@pytest.fixture
def create(repository, uow, payments, ids, clock):
    return CreateCheckout(repository, uow, payments, ids, clock)


@pytest.fixture
def webhook(repository, uow, payments, ids, clock):
    return ProcessWebhook(repository, uow, payments, ids, clock)
