from typing import Protocol


class ThumbnailUnavailable(Exception):
    """A thumbnail could not be generated; saved learning content is unaffected."""


class ThumbnailGenerator(Protocol):
    def generate(
        self, title: str, description: str, topics: tuple[str, ...], *, visual_direction: str = ""
    ) -> str:
        """Return an image reference suitable for the existing image field."""
        ...
