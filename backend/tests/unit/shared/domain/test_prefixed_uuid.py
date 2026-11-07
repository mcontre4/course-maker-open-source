import pytest
from fakes.shared.domain.fake_id_generator import FakeIdGenerator

from app.shared.domain.prefixed_uuid import PrefixedUuid


class OrderId(PrefixedUuid):
    prefix = "order_"


def test_new_uses_the_subclass_prefix() -> None:
    identifier = OrderId.new(FakeIdGenerator())

    assert str(identifier).startswith(OrderId.prefix)
    assert OrderId(str(identifier)) == identifier


def test_rejects_an_identifier_with_a_different_prefix() -> None:
    with pytest.raises(ValueError, match="order_<UUID>"):
        OrderId("user_12345678-1234-5678-1234-567812345678")
