class RecordingLessonVideo:
    def __init__(self, uow):
        self.uow = uow
        self.animations = []

    def read(self, animation):
        assert self.uow.exited, "Video preparation held a database transaction open"
        self.animations.append(animation)
        return b"saved-video"
