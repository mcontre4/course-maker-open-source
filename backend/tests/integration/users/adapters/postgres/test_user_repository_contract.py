"""PostgreSQL execution of the shared user repository contract."""

import pytest
from contracts.users.user_repository_contract import UserRepositoryContract

pytestmark = pytest.mark.integration


class TestPostgresUserRepositoryContract(UserRepositoryContract):
    """Run every repository contract test against PostgreSQL."""
