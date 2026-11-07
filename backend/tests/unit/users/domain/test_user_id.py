import pytest
from fakes.shared.domain.fake_id_generator import FakeIdGenerator

from app.users.domain.user_id import UserId


def test_new_user_id_has_the_user_prefix_and_a_uuid() -> None:
    user_id = UserId.new(FakeIdGenerator())

    assert str(user_id).startswith(UserId.prefix)
    assert UserId(str(user_id)) == user_id


@pytest.mark.parametrize("value", ["123", "order_12345678-1234-5678-1234-567812345678"])
def test_user_id_rejects_an_invalid_or_wrongly_prefixed_value(value: str) -> None:
    with pytest.raises(ValueError, match="user_<UUID>"):
        UserId(value)
