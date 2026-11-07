from app.courses.ports.thumbnails import ThumbnailUnavailable


class RecordingThumbnails:
    def __init__(self, uow, image="generated-thumbnail", *, fail=False, during=None):
        self.uow, self.image, self.fail, self.during = uow, image, fail, during
        self.calls = []
        self.visual_directions = []

    def generate(self, title, description, topics, *, visual_direction=""):
        assert self.uow.exited, "Remote generation must happen outside a transaction"
        self.calls.append((title, description, topics))
        self.visual_directions.append(visual_direction)
        if self.during:
            self.during()
        if self.fail:
            raise ThumbnailUnavailable("Provider unavailable")
        return self.image
