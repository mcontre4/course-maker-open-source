from dataclasses import asdict, replace

import pytest
from fakes.courses import InMemoryCourses
from fakes.lesson_interactive import HTML, interactive_page
from fakes.standalone import InMemoryStandaloneLessons

from app.courses.application import lesson_interactive as uc
from app.courses.application.copy_lesson import CopyLesson, CopyLessonRequest
from app.courses.application.lesson_interactive_dto import (
    ChangeInteractiveRequest,
    CreateInteractiveRequest,
    InteractiveRequest,
    LessonInteractivesRequest,
    PublicInteractivesRequest,
    PublishInteractiveRequest,
    ReorderInteractivesRequest,
    RestoreInteractiveRequest,
    SaveInteractiveDetailsRequest,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_interactive import (
    MAX_HTML_BYTES,
    InteractiveDetails,
    InteractiveId,
    InteractivePage,
)
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.courses.ports.lesson_interactive import InteractiveGenerationUnavailable

OTHER = "user_00000000-0000-0000-0000-000000000002"


def create(d, brief="Build a pendulum"):
    return d.service(uc.CreateLessonInteractive).execute(
        CreateInteractiveRequest(d.lesson_id, d.owner, brief, GenerationMode.FAST)
    )


def ref(d, item):
    return InteractiveRequest(d.lesson_id, d.owner, item.id)


def get(d, item):
    return d.service(uc.GetLessonInteractive).execute(ref(d, item))


def change(d, item, instruction="Add a reset button"):
    return d.service(uc.ChangeLessonInteractive).execute(
        ChangeInteractiveRequest(d.lesson_id, d.owner, item.id, instruction, item.revision)
    )


def publish(d, item, version=1):
    return d.service(uc.PublishInteractiveVersion).execute(
        PublishInteractiveRequest(d.lesson_id, d.owner, item.id, version)
    )


def test_build_before_outline_receives_context_and_tracks_its_own_spend(interactive_dependencies):
    d = interactive_dependencies
    created = create(d, "  Build a pendulum  ")
    assert created.brief == "Build a pendulum" and created.build.stage == "reading_lesson"
    assert created.id.startswith("interactive_") and created.html is None
    assert d.uow.commits == 1 and d.jobs.jobs
    assert d.build().completed
    item = get(d, created)
    assert item.current_version == 1 and item.published_version is None
    assert item.revision > created.revision
    assert item.title == "Gravity lab" and item.html == HTML
    assert len(item.prompts) == 2 and item.build is None and item.failure is None
    request = d.agent.calls[0]
    assert request.outline is None and request.current_html is None
    assert request.title == "Gravity" and request.description == d.lesson.description
    assert request.audience == d.lesson.audience and request.topics == ("Gravity",)
    assert request.generation_mode is GenerationMode.FAST
    assert d.tracking.calls == [(None, d.lesson_id, "interactive")]
    assert d.lessons.require_by_id(LessonId(d.lesson_id)) == d.lesson
    assert d.items.get_by_id(InteractiveId(item.id)).current_version == 1


def test_changes_preserve_live_page_and_creator_details_restore_keeps_numbering(
    interactive_dependencies,
):
    d = interactive_dependencies
    item = create(d)
    d.build()
    item = publish(d, get(d, item))
    item = d.service(uc.SaveInteractiveDetails).execute(
        SaveInteractiveDetailsRequest(
            d.lesson_id, d.owner, item.id, " My pendulum ", " Goal ", (" Try it ",), item.revision
        )
    )
    assert (item.title, item.goal, item.prompts) == ("My pendulum", "Goal", ("Try it",))
    item = change(d, item, "  Change the color  ")
    d.agent.page = interactive_page("Blue lab")
    d.build()
    item = get(d, item)
    assert d.agent.calls[-1].current_html == HTML
    assert item.current_version == 2 and item.published_version == 1
    assert item.published_html == HTML and "Blue lab" in item.html
    assert item.title == "My pendulum" and item.prompts == ("Try it",)
    item = d.service(uc.RestoreInteractiveVersion).execute(
        RestoreInteractiveRequest(d.lesson_id, d.owner, item.id, 1, item.revision)
    )
    assert item.current_version == 1 and len(item.versions) == 2
    change(d, item)
    d.build()
    item = get(d, item)
    assert [v.number for v in item.versions] == [1, 2, 3]
    assert item.current_version == 3 and item.published_version == 1
    assert all("html" not in asdict(v) for v in item.versions)


def test_first_build_preserves_details_saved_while_it_runs(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)

    def edit_details():
        d.service(uc.SaveInteractiveDetails).execute(
            SaveInteractiveDetailsRequest(
                d.lesson_id,
                d.owner,
                item.id,
                "Creator title",
                "Creator goal",
                ("Creator challenge",),
                item.revision,
            )
        )

    d.agent.during_run = edit_details
    assert d.build().completed
    saved = get(d, item)
    assert (saved.title, saved.goal, saved.prompts) == (
        "Creator title",
        "Creator goal",
        ("Creator challenge",),
    )
    persisted = d.items.get_by_id(InteractiveId(item.id))
    assert persisted.details.title == "Creator title"
    assert persisted.current_version == 1


def test_public_view_uses_only_published_html_and_live_details(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    d.build()
    item = publish(d, get(d, item))
    request = PublicInteractivesRequest(d.lesson_id)
    with pytest.raises(CourseNotFound):
        d.service(uc.GetPublicLessonInteractives).execute(request)
    d.lessons.items[d.lesson_id] = replace(
        d.lesson, content=replace(d.lesson.content, video_url="https://example.com/video.mp4")
    )
    change(d, item)
    d.agent.page = interactive_page("Draft lab")
    d.build()
    view = d.service(uc.GetPublicLessonInteractives).execute(request).items[0]
    assert view.html == HTML and view.version == 1
    assert set(asdict(view)) == {"id", "lesson_id", "version", "title", "goal", "prompts", "html"}
    publish(d, item, None)
    assert not d.service(uc.GetPublicLessonInteractives).execute(request).items


@pytest.mark.parametrize(
    "error",
    [
        InteractiveGenerationUnavailable("The provider is unavailable. Try again."),
        RuntimeError("secret-provider-token"),
    ],
)
def test_failure_and_retry_preserve_both_saved_versions(interactive_dependencies, error):
    d = interactive_dependencies
    item = create(d)
    d.build()
    item = publish(d, get(d, item))
    change(d, item, "Add weight")
    d.agent.error = error
    assert not d.build().completed
    failed = get(d, item)
    assert failed.build is None and failed.failure.request == "Add weight"
    assert "secret-provider-token" not in failed.failure.message
    assert failed.html == HTML and failed.published_html == HTML
    retried = d.service(uc.RetryInteractiveBuild).execute(ref(d, item))
    assert retried.build.request == "Add weight" and retried.failure is None
    d.agent.error = None
    assert d.build().completed and get(d, item).current_version == 2


def test_cancel_discards_late_result_and_retry_uses_new_token(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    old_job = d.jobs.jobs[-1]

    def cancel_and_retry():
        cancelled = d.service(uc.CancelInteractiveBuild).execute(ref(d, item))
        assert cancelled.build is None and cancelled.failure.request == item.brief
        d.service(uc.RetryInteractiveBuild).execute(ref(d, item))

    d.agent.during_run = cancel_and_retry
    assert not d.build(old_job).completed
    assert get(d, item).current_version is None
    assert d.jobs.jobs[-1].token != old_job.token
    d.agent.during_run = None
    assert d.build().completed
    assert not d.build(old_job).completed
    assert get(d, item).current_version == 1


def test_recovery_after_crash_can_retry_or_replace_failed_first_brief(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    d.clock.advance(901)
    stale_job = d.jobs.jobs[-1]
    items = (
        d.service(uc.ListLessonInteractives)
        .execute(LessonInteractivesRequest(d.lesson_id, d.owner))
        .items
    )
    assert items[0].build is None and "stopped" in items[0].failure.message
    assert not d.build(stale_job).completed and not d.agent.calls
    change(d, items[0], "Build a different lab")
    assert d.build().completed
    assert get(d, item).versions[0].request == "Build a different lab"


def test_revision_and_busy_conflicts_do_not_enqueue_work(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    with pytest.raises(CourseConflict, match="already running"):
        change(d, item)
    with pytest.raises(CourseConflict):
        d.service(uc.RetryInteractiveBuild).execute(ref(d, item))
    d.build()
    with pytest.raises(CourseConflict, match="changed"):
        change(d, item)
    with pytest.raises(CourseConflict):
        d.service(uc.SaveInteractiveDetails).execute(
            SaveInteractiveDetailsRequest(
                d.lesson_id, d.owner, item.id, "Title", "", (), item.revision
            )
        )
    with pytest.raises(CourseConflict):
        d.service(uc.RestoreInteractiveVersion).execute(
            RestoreInteractiveRequest(d.lesson_id, d.owner, item.id, 1, item.revision)
        )
    with pytest.raises(CourseConflict, match="no failed"):
        d.service(uc.RetryInteractiveBuild).execute(ref(d, item))
    assert len(d.jobs.jobs) == 1


def test_limit_order_deletion_and_slot_reuse(interactive_dependencies):
    d = interactive_dependencies
    items = [create(d) for _ in range(10)]
    with pytest.raises(CourseConflict, match="10"):
        create(d)
    ids = tuple(i.id for i in reversed(items))
    response = d.service(uc.ReorderLessonInteractives).execute(
        ReorderInteractivesRequest(d.lesson_id, d.owner, ids)
    )
    assert tuple(i.id for i in response.items) == ids
    assert tuple(str(i.id) for i in d.items.list_by_lesson_id(LessonId(d.lesson_id))) == ids
    with pytest.raises(CourseError):
        d.service(uc.ReorderLessonInteractives).execute(
            ReorderInteractivesRequest(d.lesson_id, d.owner, (ids[0],) * 10)
        )
    job = d.jobs.jobs[-1]
    d.service(uc.DeleteLessonInteractive).execute(ref(d, items[-1]))
    assert d.items.get_by_id(InteractiveId(items[-1].id)) is None
    assert not d.build(job).completed
    create(d)
    assert len(d.items.items) == 10


def test_ownership_lesson_binding_and_missing_versions(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    with pytest.raises(CourseNotFound):
        d.service(uc.GetLessonInteractive).execute(InteractiveRequest(d.lesson_id, OTHER, item.id))
    other_lesson = "lesson_00000000-0000-0000-0000-000000000099"
    d.lessons.items[other_lesson] = replace(
        d.lesson, content=replace(d.lesson.content, id=LessonId(other_lesson))
    )
    with pytest.raises(CourseNotFound):
        d.service(uc.GetLessonInteractive).execute(
            InteractiveRequest(other_lesson, d.owner, item.id)
        )
    with pytest.raises(CourseNotFound):
        publish(d, item, 99)
    d.build()
    item = get(d, item)
    with pytest.raises(CourseNotFound):
        d.service(uc.RestoreInteractiveVersion).execute(
            RestoreInteractiveRequest(d.lesson_id, d.owner, item.id, 99, item.revision)
        )


@pytest.mark.parametrize("queued", [False, True])
def test_enqueue_failure_is_retryable(interactive_dependencies, queued):
    d = interactive_dependencies
    if queued:
        d.jobs.error = RuntimeError("executor shut down")
    else:
        d.jobs = None
        args = (d.lessons, d.items, d.uow, d.clock, d.ids)
        d.service = lambda cls: cls(*args)
    item = create(d)
    assert item.build is None and "could not be started" in item.failure.message
    assert d.items.get_by_id(InteractiveId(item.id)).failure


def test_duplicate_worker_and_expired_during_generation_cannot_save(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    d.agent.during_run = lambda: d.clock.advance(901)
    assert not d.build().completed
    assert get(d, item).failure
    assert not d.build().completed
    assert len(d.agent.calls) == 1


def test_copy_owner_gets_history_learner_gets_only_live_version(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    d.build()
    item = publish(d, get(d, item))
    change(d, item, "Private changes")
    d.agent.page = interactive_page("Draft lab")
    d.build()
    item = get(d, item)
    original = d.items.get_by_id(InteractiveId(item.id))
    lessons = InMemoryStandaloneLessons()
    lessons.add(
        StandaloneLesson(
            LessonOwnerId(d.owner),
            "Private brief",
            replace(d.lesson.content, video_url="https://example.com/video.mp4"),
        )
    )
    copier = CopyLesson(lessons, InMemoryCourses(), d.uow, d.ids, interactives=d.items)
    for owner, count, current in [(d.owner, 2, 2), (OTHER, 1, 1)]:
        copied = copier.execute(CopyLessonRequest(d.lesson_id, owner))
        activity = d.items.list_by_lesson_id(LessonId(copied.id))[0]
        assert activity.id != original.id and len(activity.versions) == count
        assert activity.current_version == current and activity.build is None
        assert activity.published_version == 1
        if owner == OTHER:
            assert activity.brief == item.title and "Private changes" not in str(activity)
    assert d.items.get_by_id(original.id) == original


def test_copy_pending_build_retains_a_retryable_request_and_source_job(interactive_dependencies):
    d = interactive_dependencies
    item = create(d)
    source = d.items.get_by_id(InteractiveId(item.id))
    copied = source.copy(
        InteractiveId.new(d.ids),
        LessonId("lesson_00000000-0000-0000-0000-000000000099"),
        include_drafts=True,
    )
    assert copied.build is None and copied.failure.request == source.build.request
    assert "Retry" in copied.failure.message
    assert d.items.get_by_id(source.id) == source and source.build
    assert source.copy(InteractiveId.new(d.ids), source.lesson_id, include_drafts=False) is None
    assert d.build().completed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"title": ""},
        {"title": "a" * 81},
        {"goal": "g" * 201},
        {"prompts": ("",)},
        {"prompts": ("x",) * 7},
        {"prompts": ("p" * 161,)},
    ],
)
def test_details_invariants(kwargs):
    with pytest.raises(CourseError):
        InteractiveDetails(**({"title": "Title"} | kwargs))


@pytest.mark.parametrize("brief", [" ", "x" * 2001])
def test_invalid_brief_is_not_created(interactive_dependencies, brief):
    d = interactive_dependencies
    with pytest.raises(CourseError):
        create(d, brief)
    assert not d.items.items and not d.jobs.jobs


@pytest.mark.parametrize("html", ["<p>incomplete</p>", HTML + "a" * MAX_HTML_BYTES])
def test_html_limit_and_complete_document(html):
    with pytest.raises(CourseError):
        InteractivePage(html)


@pytest.mark.parametrize(
    "page",
    [
        InteractivePage(HTML),
        InteractivePage(HTML, InteractiveDetails("Title", "", ("A", "B"))),
        InteractivePage(HTML, InteractiveDetails("Title", "Goal", ("A",))),
    ],
)
def test_invalid_first_output_fails_without_version(interactive_dependencies, page):
    d = interactive_dependencies
    item = create(d)
    d.agent.page = page
    assert not d.build().completed
    assert get(d, item).failure and not get(d, item).versions
