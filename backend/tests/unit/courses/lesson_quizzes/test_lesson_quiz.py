from dataclasses import asdict, replace

import pytest
from fakes.courses import InMemoryCourses, SequenceIds
from fakes.lesson_quiz import FixedQuizClock, questions

from app.courses.application.copy_lesson import CopyLesson, CopyLessonRequest
from app.courses.application.lesson_quiz import (
    GenerateLessonQuiz,
    GetLessonQuiz,
    GetPublicLessonQuiz,
    ListLessonQuizAttempts,
    SaveLessonQuiz,
    SubmitLessonQuiz,
)
from app.courses.application.lesson_quiz_dto import (
    GenerateLessonQuizRequest,
    LessonQuizRequest,
    ListLessonQuizAttemptsRequest,
    PublicLessonQuizRequest,
    QuizQuestionInput,
    SaveLessonQuizRequest,
    SubmitLessonQuizRequest,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_quiz import LessonQuiz
from app.courses.ports.lesson_quiz import QuizGenerationUnavailable

LESSON_ID = "lesson_00000000-0000-0000-0000-000000000010"
OWNER = "user_00000000-0000-0000-0000-000000000001"
LEARNER = "user_00000000-0000-0000-0000-000000000002"


def save_request(revision=None):
    return SaveLessonQuizRequest(
        LESSON_ID, OWNER, tuple(QuizQuestionInput(**asdict(q)) for q in questions()), revision
    )


def test_generate_tracks_spend_and_preserves_media_revision(quiz_dependencies):
    lessons, quizzes, uow, agent, tracking = quiz_dependencies
    before = lessons.require_by_id(LessonId(LESSON_ID))
    generated = GenerateLessonQuiz(*quiz_dependencies).execute(
        GenerateLessonQuizRequest(LESSON_ID, OWNER, GenerationMode.FAST)
    )
    assert generated.origin == "generated"
    assert quizzes.get_by_lesson_id(before.content.id).questions == questions()
    assert lessons.require_by_id(before.content.id) == before
    assert agent.calls[0].plan == before.content.plan
    assert agent.calls[0].generation_mode is GenerationMode.FAST
    assert tracking.calls == [(None, LESSON_ID, "quiz")]
    assert uow.commits == 1


def test_replace_has_its_own_revision_and_rejects_stale_edit(quiz_dependencies):
    lessons, quizzes, uow, *_ = quiz_dependencies
    before = lessons.require_by_id(LessonId(LESSON_ID))
    save = SaveLessonQuiz(lessons, quizzes, uow)
    first = save.execute(save_request(0))
    assert first.origin == "edited"
    second = save.execute(save_request(first.revision))
    assert second.revision == 2
    with pytest.raises(CourseConflict):
        save.execute(save_request(first.revision))
    assert quizzes.get_by_lesson_id(before.content.id).revision == 2
    assert lessons.require_by_id(before.content.id) == before


def test_late_generation_cannot_overwrite_an_edit(quiz_dependencies):
    lessons, quizzes, uow, agent, tracking = quiz_dependencies
    agent.during_run = lambda: SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    with pytest.raises(CourseConflict):
        GenerateLessonQuiz(*quiz_dependencies).execute(GenerateLessonQuizRequest(LESSON_ID, OWNER))
    assert quizzes.get_by_lesson_id(LessonId(LESSON_ID)).origin == "edited"


def test_late_generation_rejects_changed_outline(quiz_dependencies):
    lessons, quizzes, uow, agent, tracking = quiz_dependencies
    before = lessons.require_by_id(LessonId(LESSON_ID))

    def change():
        lessons.save(
            replace(
                before,
                content=replace(
                    before.content,
                    plan=replace(before.content.plan, misconceptions=("Different misconception",)),
                ),
            )
        )

    agent.during_run = change
    with pytest.raises(CourseConflict):
        GenerateLessonQuiz(*quiz_dependencies).execute(GenerateLessonQuizRequest(LESSON_ID, OWNER))
    assert quizzes.get_by_lesson_id(before.content.id) is None


def test_media_completion_does_not_conflict_with_quiz_generation(quiz_dependencies):
    lessons, _, _, agent, _ = quiz_dependencies
    before = lessons.require_by_id(LessonId(LESSON_ID))
    agent.during_run = lambda: lessons.save(replace(before, revision=before.revision + 3))
    result = GenerateLessonQuiz(*quiz_dependencies).execute(
        GenerateLessonQuizRequest(LESSON_ID, OWNER)
    )
    assert result.revision == 1
    assert lessons.require_by_id(before.content.id).revision == before.revision + 3


def test_background_does_not_replace_existing_quiz_or_spend(quiz_dependencies):
    lessons, quizzes, uow, agent, tracking = quiz_dependencies
    saved = SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    result = GenerateLessonQuiz(*quiz_dependencies).execute(
        GenerateLessonQuizRequest(LESSON_ID, OWNER, only_if_missing=True)
    )
    assert result == saved
    assert not agent.calls and not tracking.calls


def test_provider_failure_preserves_existing_quiz(quiz_dependencies):
    lessons, quizzes, uow, agent, _ = quiz_dependencies
    saved = SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    agent.error = QuizGenerationUnavailable("offline")
    with pytest.raises(QuizGenerationUnavailable):
        GenerateLessonQuiz(*quiz_dependencies).execute(GenerateLessonQuizRequest(LESSON_ID, OWNER))
    assert (
        GetLessonQuiz(lessons, quizzes, uow).execute(LessonQuizRequest(LESSON_ID, OWNER)) == saved
    )


def test_answers_hidden_and_attempt_snapshot_survives_replacement(quiz_dependencies):
    lessons, quizzes, uow, *_ = quiz_dependencies
    saved = SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    public = GetPublicLessonQuiz(lessons, quizzes, uow).execute(PublicLessonQuizRequest(LESSON_ID))
    assert "correct_index" not in asdict(public.questions[0])
    assert "explanation" not in asdict(public.questions[0])
    submit = SubmitLessonQuiz(lessons, quizzes, uow, SequenceIds(), FixedQuizClock())
    attempt = submit.execute(SubmitLessonQuizRequest(LESSON_ID, LEARNER, (0,), saved.revision))
    assert (attempt.score, attempt.total, attempt.passed) == (1, 1, True)
    assert quizzes.list_attempts(LessonId(LESSON_ID), LEARNER, 20, 0)[0].score == 1
    SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    restored = ListLessonQuizAttempts(lessons, quizzes, uow).execute(
        ListLessonQuizAttemptsRequest(LESSON_ID, LEARNER)
    )
    assert restored.items == (attempt,)
    assert (
        not ListLessonQuizAttempts(lessons, quizzes, uow)
        .execute(ListLessonQuizAttemptsRequest(LESSON_ID, OWNER))
        .items
    )
    with pytest.raises(CourseConflict):
        submit.execute(SubmitLessonQuizRequest(LESSON_ID, LEARNER, (0,), saved.revision))


@pytest.mark.parametrize("answers", [(), (-1,), (True,), (3,), (0, 1)])
def test_invalid_submissions_are_not_persisted(quiz_dependencies, answers):
    lessons, quizzes, uow, *_ = quiz_dependencies
    SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    with pytest.raises(CourseError):
        SubmitLessonQuiz(lessons, quizzes, uow, SequenceIds(), FixedQuizClock()).execute(
            SubmitLessonQuizRequest(LESSON_ID, LEARNER, answers, 1)
        )
    assert not quizzes.attempts


def test_private_quiz_requires_owner_and_publication(quiz_dependencies):
    lessons, quizzes, uow, *_ = quiz_dependencies
    with pytest.raises(CourseNotFound):
        GetLessonQuiz(lessons, quizzes, uow).execute(LessonQuizRequest(LESSON_ID, LEARNER))
    before = lessons.require_by_id(LessonId(LESSON_ID))
    lessons.save(replace(before, content=replace(before.content, video_url=None)))
    with pytest.raises(CourseNotFound):
        GetPublicLessonQuiz(lessons, quizzes, uow).execute(PublicLessonQuizRequest(LESSON_ID))


def test_copy_quiz_without_attempts(quiz_dependencies):
    lessons, quizzes, uow, *_ = quiz_dependencies
    SaveLessonQuiz(lessons, quizzes, uow).execute(save_request())
    copied = CopyLesson(lessons, InMemoryCourses(), uow, SequenceIds(), quizzes).execute(
        CopyLessonRequest(LESSON_ID, OWNER)
    )
    quiz = quizzes.get_by_lesson_id(LessonId(copied.id))
    assert quiz.questions == questions()
    assert quiz.origin == "edited" and quiz.revision == 1
    assert quizzes.get_by_lesson_id(LessonId(LESSON_ID)).lesson_id != quiz.lesson_id


@pytest.mark.parametrize(
    "change",
    [
        {"options": ("same", " SAME ")},
        {"correct_index": True},
        {"correct_index": 3},
        {"kind": "essay"},
        {"prompt": "x" * 501},
        {"options": ("", "B")},
    ],
)
def test_question_invariants(change):
    with pytest.raises(CourseError):
        replace(questions()[0], **change)


def test_unique_question_identifiers():
    with pytest.raises(CourseError):
        LessonQuiz(LessonId(LESSON_ID), questions() * 2, "edited")


def test_quiz_job_is_queued_before_scripting_and_receives_fast_mode(quiz_dependencies):
    from fakes.lesson_quiz import RecordingQuizJobs
    from fakes.storyboard_agent import RecordingStoryboardAgent

    from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
    from app.courses.application.standalone_media import GenerateStandaloneStoryboard

    lessons, _, uow, *_ = quiz_dependencies
    jobs = RecordingQuizJobs()
    agent = RecordingStoryboardAgent(uow)

    def during_script():
        assert len(jobs.jobs) == 1
        assert jobs.jobs[0].generation_mode is GenerationMode.FAST

    agent.during_run = during_script
    result = GenerateStandaloneStoryboard(lessons, uow, agent, quiz_jobs=jobs).execute(
        ReviseStandaloneLessonRequest(LESSON_ID, OWNER, 0, generation_mode=GenerationMode.FAST)
    )
    assert result.content.storyboard is not None
