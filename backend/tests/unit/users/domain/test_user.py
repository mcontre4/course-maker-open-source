import pytest

from app.users.domain.errors import UserError
from app.users.domain.user import User
from app.users.domain.user_id import UserId

USER_ID = UserId("user_00000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize(
    "email,first_name,last_name",
    [
        ("invalid", "Ada", "Lovelace"),
        ("ada@", "Ada", "Lovelace"),
        ("@example.com", "Ada", "Lovelace"),
        ("ada@exa mple.com", "Ada", "Lovelace"),
        ("ada@example.com", " ", "Lovelace"),
        ("ada@example.com", "Ada", "x" * 101),
    ],
)
def test_user_rejects_invalid_details(email, first_name, last_name):
    with pytest.raises(UserError):
        User(USER_ID, email, first_name, last_name)
