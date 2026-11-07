import pytest
from sqlalchemy.orm import Session

from app.users.adapters.persistence.authentication import SqlAlchemyAccounts

pytestmark = pytest.mark.integration


def test_session_confirmation_ignores_a_stale_repeatable_read_snapshot(api, clean_mysql):
    digest = api.app.state.auth.tokens.digest(api.cookies["cm_session"])
    with Session(clean_mysql) as reader:
        accounts = SqlAlchemyAccounts(reader)
        original = accounts.get_session(digest)
        assert original is not None
        with Session(clean_mysql) as writer, writer.begin():
            SqlAlchemyAccounts(writer).delete_session(digest)
        # The default MySQL read snapshot still contains the revoked session.
        assert accounts.get_session(digest) is not None
        assert accounts.get_by_user_id(original.user_id) is not None
        assert accounts.get_session_for_authentication(digest) is None
