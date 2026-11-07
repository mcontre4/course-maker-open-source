import pytest
from fakes.courses import RecordingUnitOfWork, SequenceIds
from fakes.lesson_agent import RecordingLessonAgent
from fakes.standalone import InMemoryStandaloneLessons
from fakes.style import FixedVoiceCatalog, RecordingStylePlanner

from app.courses.application.standalone import CreateStandaloneLesson, PlanStandaloneLesson
from app.courses.application.standalone_dto import CreateStandaloneLessonRequest
from app.courses.application.style_dto import StyleInput


@pytest.fixture
def styled_lesson(request):
    repo = InMemoryStandaloneLessons()
    uow = RecordingUnitOfWork(repo)
    owner = "user_00000000-0000-0000-0000-000000000001"
    created = CreateStandaloneLesson(repo, uow, SequenceIds()).execute(
        CreateStandaloneLessonRequest(
            owner,
            "Chemical bonds",
            "Explain bonds",
            1,
            StyleInput(
                "Playful but clear",
                "Children aged 8–10",
                visual_style_id=getattr(request, "param", "flat-vector-science"),
            ),
        )
    )
    styles, voices, agent = (
        RecordingStylePlanner(uow),
        FixedVoiceCatalog(),
        RecordingLessonAgent(uow),
    )
    planner = PlanStandaloneLesson(repo, uow, agent, style_planner=styles, voices=voices)
    return repo, uow, created, styles, voices, agent, planner
