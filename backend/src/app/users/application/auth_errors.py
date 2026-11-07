class AuthenticationError(Exception):
    """Credentials, session or one-time action could not be authenticated."""


class AccountConflictError(Exception):
    """An existing account must be authenticated through its original provider."""


class AuthenticationUnavailableError(Exception):
    """An authentication dependency is unavailable; fail closed."""
