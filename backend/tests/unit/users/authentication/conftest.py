import pytest
from fakes.authentication import auth_dependencies


@pytest.fixture
def auth():
    return auth_dependencies()
