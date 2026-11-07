from dataclasses import asdict

import pytest
from fakes.courses import RecordingStorage

from app.courses.application import use_cases as uc
from app.courses.application.assets import (
    CreateAssetUpload,
    DownloadAssetRequest,
    GetAssetDownload,
    UploadAssetRequest,
)
from app.courses.application.dto import DurationRequest
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import CourseId


def test_create_and_list_persisted_drafts(dependencies, draft, services):
    repo, uow, _ = dependencies
    saved = repo.require_by_id(CourseId(draft.id))
    assert saved.title == "Python" and saved.chapters == ()
    assert uow.commits == 1
    page = services.list.execute(uc.ListCoursesRequest(search="python", limit=1))
    assert page.total == 1 and page.items == (draft,)
    assert services.get.execute(uc.CourseRequest(draft.id)) == draft
    assert uc.GetProgress(*dependencies).execute(uc.CourseRequest(draft.id)).percent == 0


def test_update_then_delete(dependencies, draft):
    repo, _, _ = dependencies
    result = uc.UpdateCourse(*dependencies).execute(
        uc.UpdateCourseRequest(
            draft.id, "New title", "New goal", DurationRequest("weekly", weeks=2, hours_per_week=3)
        )
    )
    assert repo.require_by_id(CourseId(draft.id)).title == result.title == "New title"
    assert uc.DeleteCourse(*dependencies).execute(uc.CourseRequest(draft.id)).deleted
    assert repo.get_by_id(CourseId(draft.id)) is None


def test_missing_course(dependencies):
    with pytest.raises(CourseNotFound):
        uc.GetCourse(*dependencies).execute(
            uc.CourseRequest("course_00000000-0000-0000-0000-000000000001")
        )


def test_manual_syllabus_has_server_ids_and_hides_answer_keys(dependencies, outlined):
    lesson = outlined.chapters[0].lessons[0]
    assert lesson.id.startswith("lesson_")
    assert set(asdict(lesson.quiz[0])) == {"id", "prompt", "options"}
    assert (
        uc.GetLesson(*dependencies).execute(uc.LessonLookupRequest(outlined.id, lesson.id))
        == lesson
    )


def test_edit_topic_and_protect_ready_syllabus(dependencies, outlined):
    lesson = outlined.chapters[0].lessons[0]
    request = uc.EditTopicRequest(outlined.id, lesson.id, "Values", "add")
    updated = uc.EditSyllabusTopic(*dependencies).execute(request)
    assert updated.chapters[0].lessons[0].topics == ("Names", "Values")
    uc.ApproveSyllabus(*dependencies).execute(uc.CourseRequest(outlined.id))
    with pytest.raises(CourseConflict):
        uc.EditSyllabusTopic(*dependencies).execute(request)
    assert dependencies[1].rollbacks == 1


def test_quiz_requires_review_and_persists_attempts_and_progress(dependencies, ready):
    repo, uow, _ = dependencies
    lesson_id = ready.chapters[0].lessons[0].id
    request = uc.SubmitQuizRequest(ready.id, lesson_id, (0,))
    with pytest.raises(CourseConflict):
        uc.SubmitQuiz(*dependencies).execute(request)
    assert uow.rollbacks == 1
    uc.ReviewLesson(*dependencies).execute(uc.LessonLookupRequest(ready.id, lesson_id))
    failed = uc.SubmitQuiz(*dependencies).execute(uc.SubmitQuizRequest(ready.id, lesson_id, (1,)))
    assert not failed.passed and failed.course.completed == ()
    passed = uc.SubmitQuiz(*dependencies).execute(request)
    assert passed.passed and passed.feedback[0].explanation == "x names a value"
    persisted = repo.require_by_id(CourseId(ready.id))
    assert len(persisted.attempts) == 2 and persisted.completed == (lesson_id,)
    assert uc.GetProgress(*dependencies).execute(uc.CourseRequest(ready.id)).percent == 100
    uc.SubmitQuiz(*dependencies).execute(request)
    assert len(repo.require_by_id(CourseId(ready.id)).completed) == 1


def test_invalid_quiz_does_not_change_progress(dependencies, ready):
    lesson_id = ready.chapters[0].lessons[0].id
    uc.ReviewLesson(*dependencies).execute(uc.LessonLookupRequest(ready.id, lesson_id))
    with pytest.raises(CourseError):
        uc.SubmitQuiz(*dependencies).execute(uc.SubmitQuizRequest(ready.id, lesson_id, (99,)))
    assert dependencies[0].require_by_id(CourseId(ready.id)).attempts == ()


def test_invalid_topic_rolls_back(dependencies, outlined):
    lesson_id = outlined.chapters[0].lessons[0].id
    with pytest.raises(CourseError):
        uc.EditSyllabusTopic(*dependencies).execute(
            uc.EditTopicRequest(outlined.id, lesson_id, "Names", "remove")
        )
    assert dependencies[0].require_by_id(CourseId(outlined.id)).lesson(lesson_id).topics == (
        "Names",
    )


def test_asset_calls_happen_after_database_scope_exits(dependencies, draft):
    repo, uow, ids = dependencies
    storage = RecordingStorage(uow)
    result = CreateAssetUpload(repo, storage, ids, uow).execute(
        UploadAssetRequest(draft.id, "image/png", 123)
    )
    assert result.method == "PUT" and result.expires_in == 900
    assert ("x-goog-if-generation-match", "0") in result.required_headers
    assert storage.calls[0] == (f"courses/{draft.id}/{result.id}", "image/png", 123)
    download = GetAssetDownload(repo, storage, uow).execute(
        DownloadAssetRequest(draft.id, result.id)
    )
    assert download.method == "GET"
    with pytest.raises(ValueError):
        GetAssetDownload(repo, storage, uow).execute(
            DownloadAssetRequest(draft.id, "../../private")
        )


@pytest.mark.parametrize(
    "content_type,size",
    [
        ("text/html", 100),
        ("image/png", 0),
        ("video/mp4", 524288001),
        ("image/png", True),
        ("image/png", 1.5),
    ],
)
def test_invalid_upload(dependencies, draft, content_type, size):
    repo, uow, ids = dependencies
    storage = RecordingStorage(uow)
    with pytest.raises(CourseError):
        CreateAssetUpload(repo, storage, ids, uow).execute(
            UploadAssetRequest(draft.id, content_type, size)
        )
    assert storage.calls == []


def test_supply_content_after_approval_and_freeze_after_review(dependencies, ready):
    lesson_id = ready.chapters[0].lessons[0].id
    asset_id = "asset_00000000-0000-0000-0000-000000000123"
    original = dependencies[0].require_by_id(CourseId(ready.id)).lesson(lesson_id)
    from app.courses.application.dto import QuestionRequest

    quiz = tuple(
        QuestionRequest(q.prompt, q.options, q.answer, q.explanation) for q in original.quiz
    )
    request = uc.UpdateLessonContentRequest(ready.id, lesson_id, None, quiz, asset_id)
    result = uc.UpdateLessonContent(*dependencies).execute(request)
    assert result.chapters[0].lessons[0].video_asset_id == asset_id
    uc.ReviewLesson(*dependencies).execute(uc.LessonLookupRequest(ready.id, lesson_id))
    uc.SubmitQuiz(*dependencies).execute(uc.SubmitQuizRequest(ready.id, lesson_id, (0,)))
    attempts = uc.GetQuizAttempts(*dependencies).execute(
        uc.LessonLookupRequest(ready.id, lesson_id)
    )
    assert len(attempts.items) == 1 and attempts.items[0].passed
    with pytest.raises(CourseConflict):
        uc.UpdateLessonContent(*dependencies).execute(request)


def test_catalog_uses_injected_port():
    from app.courses.application.catalog import CatalogRequest, GetCatalog
    from app.courses.ports.catalog import Catalog

    class StaticCatalog:
        def topics(self):
            return ("Technology", "Art")

    catalog: Catalog = StaticCatalog()
    assert GetCatalog(catalog).execute(CatalogRequest()).topics == ("Technology", "Art")


def test_editing_one_topic_preserves_all_other_lessons(dependencies, syllabus_request):
    from dataclasses import replace

    chapter = syllabus_request.chapters[0]
    second_lesson = replace(chapter.lessons[0], title="Functions", topics=("Calls",))
    request = replace(
        syllabus_request, chapters=(replace(chapter, lessons=(*chapter.lessons, second_lesson)),)
    )
    outlined = uc.ReplaceSyllabus(*dependencies).execute(request)
    first, second = outlined.chapters[0].lessons
    updated = uc.EditSyllabusTopic(*dependencies).execute(
        uc.EditTopicRequest(outlined.id, first.id, "Values", "add")
    )
    assert updated.chapters[0].lessons[0].topics == ("Names", "Values")
    assert updated.chapters[0].lessons[1] == second
