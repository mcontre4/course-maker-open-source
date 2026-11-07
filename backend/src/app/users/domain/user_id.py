"""Typed, externally safe identifiers for users."""

from app.shared.domain.prefixed_uuid import PrefixedUuid


class UserId(PrefixedUuid):
    """A user identifier in the canonical ``user_<UUID>`` format."""

    prefix = "user_"
