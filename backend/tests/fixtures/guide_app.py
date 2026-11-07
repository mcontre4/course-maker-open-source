from fakes.guide_model import scripted_guide
from fakes.lesson_quiz import RecordingQuizAgent
from fakes.spend import FixedBilling, InMemorySpend
from fastapi import FastAPI
from fixtures.lesson_plan import lesson_plan
from fixtures.syllabus import curriculum
from sqlalchemy.orm import Session

from app.courses.adapters.http import learning_activity
from app.courses.adapters.http.creators import router as creator_router
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.http.guide import router as guide_router
from app.courses.adapters.http.router import router as course_router
from app.courses.adapters.http.standalone import get_owner
from app.courses.adapters.http.standalone import router as lesson_router
from app.courses.composition import install_dependencies
from app.courses.ports.lesson_agent import LessonAgentResponse
from app.courses.ports.syllabus_agent import SyllabusAgentResponse
from app.shared.infrastructure.database import get_session

OWNER = "user_00000000-0000-0000-0000-000000000001"


def build_guide_test_app(
    engine,
    model_script,
    owner=OWNER,
    media=None,
    interactive_agent=None,
    interactive_workers=None,
    redis_client=None,
):
    app = FastAPI()
    sessions = []

    def session():
        with Session(engine) as scoped:
            sessions.append(scoped)
            yield scoped

    class Specialist:
        def __init__(self):
            self.calls = []

        def run(self, request):
            # Browser polling uses independent concurrent sessions; the non-browser
            # integration fixture retains its strict transaction-boundary assertion.
            if media is None:
                assert not any(s.in_transaction() for s in sessions)
            self.calls.append(request)
            from dataclasses import replace

            plan = lesson_plan(request.brief)
            if "changed" in request.message:
                plan = replace(plan, beats=(replace(plan.beats[0], title="Changed introduction"),))
            return LessonAgentResponse(plan, "test-specialist", 1, 0, 100)

    specialist = Specialist()

    class SyllabusSpecialist:
        def run(self, request):
            from dataclasses import replace

            assert not any(s.in_transaction() for s in sessions)
            plan = curriculum()
            if "changed" in request.message:
                plan = replace(plan, title="Updated course")
            return SyllabusAgentResponse("Syllabus revised", plan, "[]")

    install_dependencies(
        app,
        lambda: None,
        lambda: redis_client,
        lambda: SyllabusSpecialist(),
        lambda: specialist,
        lambda: media.storyboard if media else None,
        lambda: media.speech if media else None,
        lambda: media if media else None,
        guide_agent=lambda: scripted_guide(model_script),
        spend=InMemorySpend,
        billing=FixedBilling,
        voice_catalog=(lambda: media) if media else None,
        interactive_agent=(lambda: interactive_agent) if interactive_agent else None,
        interactive_workers=(lambda: interactive_workers) if interactive_workers else None,
        quiz_agent=(lambda: RecordingQuizAgent()) if media else None,
    )
    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_owner] = lambda: owner
    register_error_handlers(app)
    app.include_router(lesson_router)
    app.include_router(guide_router)
    app.include_router(course_router)
    app.include_router(creator_router)
    from app.courses.adapters.http.lesson_interactive import public_router, router
    from app.courses.adapters.http.lesson_quiz import public_router as public_quizzes
    from app.courses.adapters.http.lesson_quiz import router as quizzes

    app.include_router(router)
    app.include_router(public_router)
    app.include_router(quizzes)
    app.include_router(public_quizzes)
    app.include_router(learning_activity.router)
    if media:
        from typing import Annotated

        from fastapi import Depends

        from app.courses.adapters.http import lesson_video, outline, style, video
        from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
        from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
        from app.courses.application.lesson_playback import GetStandaloneLessonPlayback
        from app.courses.application.lesson_video import GetStandaloneLessonVideo

        def video_reader(scoped: Annotated[Session, Depends(get_session)]):
            return GetStandaloneLessonVideo(
                SqlAlchemyStandaloneLessons(scoped), media, CourseUnitOfWork(scoped)
            )

        def playback_reader(scoped: Annotated[Session, Depends(get_session)]):
            return GetStandaloneLessonPlayback(
                SqlAlchemyStandaloneLessons(scoped), media, CourseUnitOfWork(scoped)
            )

        app.dependency_overrides[lesson_video.get_standalone_video_reader] = video_reader
        app.dependency_overrides[lesson_video.get_standalone_playback] = playback_reader
        app.include_router(video.router)
        app.include_router(outline.router)
        app.include_router(style.router)
        app.include_router(lesson_video.router)
    return app, specialist
