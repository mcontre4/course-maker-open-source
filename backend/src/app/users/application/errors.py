"""Application failures for the users domain."""


class EmailAlreadyRegisteredError(Exception):
    """Raised when attempting to register an existing email address."""
