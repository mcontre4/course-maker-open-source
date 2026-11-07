import pytest
from fakes.courses import RecordingUnitOfWork, SequenceIds
from fakes.lesson_agent import RecordingLessonAgent
from fakes.standalone import InMemoryStandaloneLessons

from app.courses.application.standalone import CreateStandaloneLesson, PlanStandaloneLesson
from app.courses.application.standalone_dto import CreateStandaloneLessonRequest

OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.fixture
def standalone():
    repository = InMemoryStandaloneLessons()
    uow = RecordingUnitOfWork(repository)
    agent = RecordingLessonAgent(uow)
    created = CreateStandaloneLesson(repository, uow, SequenceIds()).execute(
        CreateStandaloneLessonRequest(OWNER, "Chemical bonds", "Explain bonds for a beginner", 3)
    )
    return repository, uow, agent, PlanStandaloneLesson(repository, uow, agent), created


@pytest.fixture
def voiced_standalone(standalone):
    from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
    from fakes.storyboard_agent import RecordingStoryboardAgent

    from app.courses.application.standalone import ApproveStandaloneLesson
    from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
    from app.courses.application.standalone_media import (
        GenerateStandaloneSpeech,
        GenerateStandaloneStoryboard,
    )
    from app.courses.domain.identifiers import LessonId
    from app.courses.domain.speech import SpeechSettings

    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0))
    approved = ApproveStandaloneLesson(repo, uow).execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, planned.revision)
    )
    scripted = GenerateStandaloneStoryboard(repo, uow, RecordingStoryboardAgent(uow)).execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, approved.revision)
    )
    provider = RecordingSpeech(uow)
    artifacts = InMemorySpeechArtifacts(uow)
    service = GenerateStandaloneSpeech(repo, uow, provider, artifacts, SpeechSettings("voice"))
    service.execute(ReviseStandaloneLessonRequest(created.id, OWNER, scripted.revision))
    before = repo.require_by_id(LessonId(created.id))
    return service, repo, provider, artifacts, before


@pytest.fixture
def completed_standalone(voiced_standalone):
    from dataclasses import replace

    from app.courses.domain.animation import AnimationProject

    _, repo, _, _, before = voiced_standalone
    project = AnimationProject(
        str(before.content.id),
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "test",
        before.content.alignment.duration_sec,
        review_status="approved",
    )
    completed = before.save_media(replace(before.content, animation=project))
    repo.save(completed)
    return repo, completed


@pytest.fixture
def video_pipeline(standalone):
    from fakes.animator import RecordingAnimator
    from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
    from fakes.storyboard_agent import RecordingStoryboardAgent

    from app.courses.application.generate_video import GenerateStandaloneVideo
    from app.courses.application.standalone import ApproveStandaloneLesson
    from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
    from app.courses.application.standalone_media import (
        GenerateStandaloneAnimation,
        GenerateStandaloneSpeech,
        GenerateStandaloneStoryboard,
    )
    from app.courses.domain.speech import SpeechSettings

    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0))
    board, speech, animator = (
        RecordingStoryboardAgent(uow),
        RecordingSpeech(uow),
        RecordingAnimator(uow),
    )
    artifacts = InMemorySpeechArtifacts(uow)
    video = GenerateStandaloneVideo(
        ApproveStandaloneLesson(repo, uow),
        GenerateStandaloneStoryboard(repo, uow, board),
        GenerateStandaloneSpeech(repo, uow, speech, artifacts, SpeechSettings("test-voice")),
        GenerateStandaloneAnimation(repo, uow, animator, artifacts),
    )
    result = video.execute(ReviseStandaloneLessonRequest(created.id, OWNER, planned.revision))
    return video, repo, board, speech, animator, artifacts, result
