from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest

from app.users.application import authentication as uc
from app.users.application.auth_errors import AccountConflictError, AuthenticationError
from app.users.domain.authentication import Account, validate_password
from app.users.domain.errors import UserError
from app.users.domain.user_id import UserId

EMAIL = "person@example.com"
PASSWORD = "a unique long passphrase 47!"
NEW_PASSWORD = "another unique passphrase 98!"


def signup(auth, email=EMAIL):
    return uc.SignUp(auth, auth.clock).execute(uc.SignUpRequest(email, PASSWORD, "Ada", "Lovelace"))


def mail_token(auth):
    url = auth.accounts.mail[-1].body.splitlines()[2]
    return parse_qs(urlsplit(url).fragment)["token"][0]


def verify(auth):
    uc.CompleteEmailAction(auth, auth.clock).execute(uc.CompleteActionRequest(mail_token(auth)))


def signin(auth, previous=""):
    return uc.SignIn(auth, auth.clock).execute(uc.SignInRequest(EMAIL, PASSWORD, previous))


def test_signup_normalizes_email_hashes_password_and_atomically_queues_verification(auth):
    result = signup(auth, " Person@Example.com ")
    account = auth.accounts.get_by_email(EMAIL)
    user = auth.users.get_by_id(account.user_id)
    assert (user.email, user.first_name, user.last_name) == (EMAIL, "Ada", "Lovelace")
    assert account.password_hash != PASSWORD
    assert not account.verified
    assert auth.uow.commits == 1
    token = mail_token(auth)
    assert token not in auth.accounts.actions
    assert auth.tokens.digest(token) in auth.accounts.actions
    assert "receive an email" in result.message


def test_duplicate_signup_has_same_response_and_preserves_credentials(auth):
    first = signup(auth)
    before = auth.accounts.get_by_email(EMAIL)
    assert signup(auth, "PERSON@example.com") == first
    assert auth.accounts.get_by_email(EMAIL) == before
    assert len(auth.accounts.mail) == 1


def test_concurrent_duplicate_rolls_back_user_and_outbox(auth):
    auth.accounts.fail_add = True
    signup(auth)
    assert auth.users.get_by_email(EMAIL) is None
    assert not auth.accounts.accounts and not auth.accounts.mail
    assert auth.uow.commits == 0


@pytest.mark.parametrize("password", ["short", "a" * 129, "passwordpassword", "1" * 30])
def test_password_policy_rejects_weak_or_oversized_passwords(password):
    with pytest.raises(UserError):
        validate_password(password)


def test_passphrases_unicode_and_whitespace_are_supported():
    validate_password("  Rêver ensemble 🌙 2026  ")


def test_configured_common_password_list_is_applied():
    with pytest.raises(UserError, match="less common"):
        validate_password(
            "Known Compromised Passphrase", frozenset({"known compromised passphrase"})
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "UPPER@example.com", "password_hash": "encoded"},
        {"email": EMAIL},
        {"email": "invalid", "google_subject": "subject"},
    ],
)
def test_account_invariants(changes):
    with pytest.raises(UserError):
        Account(UserId("user_00000000-0000-0000-0000-000000000001"), **changes)


@pytest.mark.parametrize(
    "email,password", [(EMAIL, "incorrect"), ("missing@example.com", PASSWORD)]
)
def test_invalid_credentials_do_not_create_session(auth, email, password):
    signup(auth)
    verify(auth)
    with pytest.raises(AuthenticationError):
        uc.SignIn(auth, auth.clock).execute(uc.SignInRequest(email, password))
    assert not auth.accounts.sessions


def test_verification_is_required_and_single_use(auth):
    signup(auth)
    with pytest.raises(AuthenticationError):
        signin(auth)
    token = mail_token(auth)
    verify(auth)
    assert auth.accounts.get_by_email(EMAIL).verified
    with pytest.raises(AuthenticationError):
        uc.CompleteEmailAction(auth, auth.clock).execute(uc.CompleteActionRequest(token))


def test_signin_rotates_token_and_logout_revokes_it(auth):
    signup(auth)
    verify(auth)
    first = signin(auth)
    second = signin(auth, first.session_token)
    assert second.user.email == EMAIL
    assert auth.tokens.digest(first.session_token) not in auth.accounts.sessions
    assert second.session_token not in auth.accounts.sessions
    assert (
        uc.GetSession(auth, auth.clock).execute(uc.SessionRequest(second.session_token)).id
        == second.user.id
    )
    uc.SignOut(auth, auth.clock).execute(uc.SessionRequest(second.session_token))
    with pytest.raises(AuthenticationError):
        uc.GetSession(auth, auth.clock).execute(uc.SessionRequest(second.session_token))


@pytest.mark.parametrize("elapsed", [1800, 28800])
def test_session_idle_and_absolute_expiry(auth, elapsed):
    signup(auth)
    verify(auth)
    result = signin(auth)
    auth.clock.timestamp += elapsed
    with pytest.raises(AuthenticationError):
        uc.GetSession(auth, auth.clock).execute(uc.SessionRequest(result.session_token))


def test_activity_extends_idle_timeout_without_extending_absolute_lifetime(auth):
    signup(auth)
    verify(auth)
    result = signin(auth)
    original = auth.accounts.get_session(auth.tokens.digest(result.session_token))
    auth.clock.timestamp += 1700
    uc.GetSession(auth, auth.clock).execute(uc.SessionRequest(result.session_token))
    current = auth.accounts.get_session(original.digest)
    assert current.last_seen_at == auth.clock.timestamp
    assert current.expires_at == original.expires_at


def test_reset_is_single_use_and_revokes_all_sessions(auth):
    signup(auth)
    verify(auth)
    sessions = [signin(auth), signin(auth)]
    uc.RequestEmailAction(auth, auth.clock).execute(uc.EmailActionRequest(EMAIL, "reset"))
    token = mail_token(auth)
    uc.CompleteEmailAction(auth, auth.clock).execute(
        uc.CompleteActionRequest(token, "reset", NEW_PASSWORD)
    )
    assert not auth.accounts.sessions
    for session in sessions:
        with pytest.raises(AuthenticationError):
            uc.GetSession(auth, auth.clock).execute(uc.SessionRequest(session.session_token))
    with pytest.raises(AuthenticationError):
        signin(auth)
    result = uc.SignIn(auth, auth.clock).execute(uc.SignInRequest(EMAIL, NEW_PASSWORD))
    assert result.user.verified
    with pytest.raises(AuthenticationError):
        uc.CompleteEmailAction(auth, auth.clock).execute(
            uc.CompleteActionRequest(token, "reset", NEW_PASSWORD)
        )


def test_expired_and_wrong_purpose_actions_fail_without_mutating_account(auth):
    signup(auth)
    token = mail_token(auth)
    action = uc.CompleteEmailAction(auth, auth.clock)
    with pytest.raises(AuthenticationError):
        action.execute(uc.CompleteActionRequest(token, "reset", NEW_PASSWORD))
    assert not auth.accounts.get_by_email(EMAIL).verified
    auth.clock.timestamp += 86400
    with pytest.raises(AuthenticationError):
        action.execute(uc.CompleteActionRequest(token))


def test_resend_replaces_link_and_unknown_email_response_is_generic(auth):
    signup(auth)
    old = mail_token(auth)
    use_case = uc.RequestEmailAction(auth, auth.clock)
    assert use_case.execute(uc.EmailActionRequest(EMAIL, "verify")) == use_case.execute(
        uc.EmailActionRequest("missing@example.com", "verify")
    )
    with pytest.raises(AuthenticationError):
        uc.CompleteEmailAction(auth, auth.clock).execute(uc.CompleteActionRequest(old))
    verify(auth)
    count = len(auth.accounts.mail)
    use_case.execute(uc.EmailActionRequest(EMAIL, "verify"))
    assert len(auth.accounts.mail) == count


@pytest.mark.parametrize("purpose", ["delete", "other"])
def test_unsupported_email_action_is_rejected(auth, purpose):
    with pytest.raises(AuthenticationError):
        uc.RequestEmailAction(auth, auth.clock).execute(uc.EmailActionRequest(EMAIL, purpose))
    with pytest.raises(AuthenticationError):
        uc.CompleteEmailAction(auth, auth.clock).execute(uc.CompleteActionRequest("token", purpose))


def test_google_signup_and_repeat_signin_use_immutable_subject(auth):
    start = uc.BeginGoogleSignIn(auth, auth.clock).execute(uc.BeginGoogleRequest())
    complete = uc.CompleteGoogleSignIn(auth, auth.clock)
    result = complete.execute(uc.CompleteGoogleRequest(start.state, "valid-code"))
    assert result.user.verified
    assert auth.accounts.get_by_email("google@example.com").password_hash is None
    auth.google.identity = replace(auth.google.identity, email="new-address@example.com")
    again = uc.BeginGoogleSignIn(auth, auth.clock).execute(uc.BeginGoogleRequest())
    assert (
        complete.execute(uc.CompleteGoogleRequest(again.state, "valid-code")).user.id
        == result.user.id
    )
    with pytest.raises(AuthenticationError):
        complete.execute(uc.CompleteGoogleRequest(start.state, "valid-code"))


def test_google_never_links_an_existing_email_without_authentication(auth):
    signup(auth, "google@example.com")
    start = uc.BeginGoogleSignIn(auth, auth.clock).execute(uc.BeginGoogleRequest())
    with pytest.raises(AccountConflictError):
        uc.CompleteGoogleSignIn(auth, auth.clock).execute(
            uc.CompleteGoogleRequest(start.state, "valid-code")
        )
    assert not auth.accounts.get_by_email("google@example.com").google_subject
    assert not auth.accounts.sessions


def test_google_failure_consumes_flow_without_creating_account(auth):
    start = uc.BeginGoogleSignIn(auth, auth.clock).execute(uc.BeginGoogleRequest())
    with pytest.raises(AuthenticationError):
        uc.CompleteGoogleSignIn(auth, auth.clock).execute(
            uc.CompleteGoogleRequest(start.state, "invalid")
        )
    assert not auth.accounts.accounts
    assert start.state not in auth.flows.items
