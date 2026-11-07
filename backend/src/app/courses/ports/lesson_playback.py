from typing import Protocol

from app.courses.domain.animation import AnimationProject


class LessonPlayback(Protocol):
    def video_ready(self, animation: AnimationProject) -> bool: ...

    def preview(self, animation: AnimationProject) -> str: ...
