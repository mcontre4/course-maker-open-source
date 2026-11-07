from dataclasses import replace

from app.courses.application.generate_video import GenerateStandaloneVideo
from app.courses.application.standalone import PlanStandaloneLesson
from app.courses.application.standalone_dto import (
    ReviseStandaloneLessonRequest,
    StandaloneLessonResponse,
)


class GenerateAutomaticLesson:
    def __init__(self, planner: PlanStandaloneLesson, video: GenerateStandaloneVideo) -> None:
        self._planner, self._video = planner, video

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        current = self._planner.execute(request)
        if current.content.plan and current.content.plan.feasibility_status == "infeasible":
            return current
        return self._video.execute(replace(request, expected_revision=current.revision))
