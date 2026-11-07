"""Deterministic account ports; no monkey patching or infrastructure."""

import hashlib
from copy import deepcopy
from datetime import UTC, datetime

from fakes.courses import SequenceIds
from fakes.users.adapters.in_memory.user_repository import InMemoryUserRepository

from app.users.application import authentication as uc
from app.users.application.auth_errors import AuthenticationError
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.ports.authentication import GoogleIdentity


class MutableAuthClock:
    def __init__(self):
        self.timestamp = 1800000000.0

    def now(self):
        return datetime.fromtimestamp(self.timestamp, UTC)


class SequenceTokens:
    def __init__(self):
        self.counter = 0

    def new(self):
        self.counter += 1
        return f"opaque-token-{self.counter:032d}"

    def digest(self, token):
        return hashlib.sha256(token.encode()).hexdigest()


class FakePasswords:
    def hash(self, password):
        return "encoded:" + password

    def verify(self, password, encoded):
        return bool(encoded and encoded == self.hash(password))


class InMemoryAccounts:
    def __init__(self):
        self.accounts = {}
        self.sessions = {}
        self.actions = {}
        self.mail = []
        self.fail_add = False

    def get_by_email(self, email):
        return next((a for a in self.accounts.values() if a.email == email), None)

    def get_by_google_subject(self, subject):
        return next((a for a in self.accounts.values() if a.google_subject == subject), None)

    def get_by_user_id(self, user_id):
        return self.accounts.get(user_id)

    def add(self, account):
        if self.fail_add:
            raise EmailAlreadyRegisteredError()
        self.accounts[account.user_id] = account

    def save(self, account):
        self.accounts[account.user_id] = account

    def add_session(self, session):
        self.sessions[session.digest] = session

    def get_session(self, digest):
        return self.sessions.get(digest)

    def get_session_for_authentication(self, digest):
        return self.get_session(digest)

    def save_session(self, session):
        if session.digest in self.sessions:
            self.sessions[session.digest] = session

    def delete_session(self, digest):
        self.sessions.pop(digest, None)

    def revoke_sessions(self, user_id):
        self.sessions = {k: v for k, v in self.sessions.items() if v.user_id != user_id}

    def add_action(self, action):
        self.actions[action.digest] = action

    def consume_action(self, digest, purpose, now):
        action = self.actions.get(digest)
        if action and action.purpose == purpose and action.expires_at > now:
            return self.actions.pop(digest)
        return None

    def delete_actions(self, user_id, purpose):
        self.actions = {
            k: v for k, v in self.actions.items() if v.user_id != user_id or v.purpose != purpose
        }

    def enqueue_mail(self, mail):
        self.mail.append(mail)


class AuthUnitOfWork:
    def __init__(self, accounts, users):
        self.accounts, self.users = accounts, users
        self.active = False
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        self.active, self.committed = True, False
        self.snapshot = deepcopy((self.accounts.__dict__, self.users.__dict__))
        return self

    def __exit__(self, exception_type, exception, traceback):
        if exception_type or not self.committed:
            self.accounts.__dict__, self.users.__dict__ = self.snapshot
            self.rollbacks += 1
        self.active = False

    def commit(self):
        self.committed = True
        self.commits += 1

    def rollback(self):
        self.accounts.__dict__, self.users.__dict__ = self.snapshot
        self.rollbacks += 1


class InMemoryGoogleFlows:
    def __init__(self):
        self.items = {}

    def put(self, state, flow):
        self.items[state] = flow

    def consume(self, state):
        return self.items.pop(state, None)


class ScriptedGoogle:
    def __init__(self, uow=None):
        self.identity = GoogleIdentity("google-subject", "google@example.com", "Google", "User")
        self.uow = uow
        self.calls = []

    def authorization_url(self, state, flow):
        return "https://accounts.google.com/o/oauth2/v2/auth?state=" + state

    def exchange(self, code, flow):
        if self.uow:
            assert not self.uow.active
        self.calls.append((code, flow))
        if code != "valid-code":
            raise AuthenticationError()
        return self.identity


def auth_dependencies():
    accounts, users = InMemoryAccounts(), InMemoryUserRepository()
    uow = AuthUnitOfWork(accounts, users)
    return uc.AuthDependencies(
        accounts,
        users,
        uow,
        MutableAuthClock(),
        SequenceIds(),
        FakePasswords(),
        SequenceTokens(),
        InMemoryGoogleFlows(),
        ScriptedGoogle(uow),
        uc.AuthPolicy("https://app.example.com"),
    )
