from dataclasses import asdict, replace

import pytest
from fakes.courses import SequenceIds
from fakes.thumbnails import RecordingThumbnails

from app.courses.application.standalone import CreateStandaloneLesson, PlanStandaloneLesson
from app.courses.application.standalone_dto import (
    CreateStandaloneLessonRequest,
    ReviseStandaloneLessonRequest,
)
from app.courses.application.thumbnails import GenerateStandaloneThumbnail, ThumbnailRequest
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.identifiers import LessonId
from app.courses.domain.style import LessonStyle
from app.courses.domain.visual_style import VisualStyle
from app.courses.ports.lesson_agent import LessonGenerationUnavailable
from app.courses.ports.thumbnails import ThumbnailUnavailable


def test_draft_is_saved_without_waiting_for_generation(standalone):
    repository, uow, _, _, existing = standalone
    ids = SequenceIds()
    ids.new_uuid()
    result = CreateStandaloneLesson(repository, uow, ids).execute(
        CreateStandaloneLessonRequest(existing.owner_id, "Inertia", "Explain inertia", 3)
    )
    saved = repository.require_by_id(LessonId(result.id))
    assert saved.content.image == ""
    assert saved.content.plan is None
    assert saved.content.title == "Inertia"
    assert not saved.approved


@pytest.mark.parametrize("fail", [False, True])
def test_planning_generates_thumbnail_after_creation_and_survives_image_failure(standalone, fail):
    repository, uow, agent, _, draft = standalone
    generator = RecordingThumbnails(uow, fail=fail)

    def require_thumbnail_saved_before_outline():
        saved = repository.require_by_id(LessonId(draft.id))
        assert saved.content.image == ("" if fail else "generated-thumbnail")
        assert saved.content.plan is None

    agent.during_run = require_thumbnail_saved_before_outline
    planner = PlanStandaloneLesson(repository, uow, agent, thumbnails=generator)
    result = planner.execute(ReviseStandaloneLessonRequest(draft.id, draft.owner_id, 0, "Plan"))
    saved = repository.require_by_id(LessonId(draft.id))
    assert saved.content.image == ("" if fail else "generated-thumbnail")
    assert saved.content.plan is not None
    assert result.revision == (1 if fail else 2)
    if not fail:
        agent.during_run = None
        planner.execute(
            ReviseStandaloneLessonRequest(draft.id, draft.owner_id, result.revision, "Refine")
        )
        assert len(generator.calls) == 1


def test_outline_failure_preserves_thumbnail_and_retry_reuses_it(standalone):
    repository, uow, agent, _, draft = standalone
    generator = RecordingThumbnails(uow)
    planner = PlanStandaloneLesson(repository, uow, agent, thumbnails=generator)
    agent.error = LessonGenerationUnavailable("Provider unavailable")
    with pytest.raises(LessonGenerationUnavailable):
        planner.execute(ReviseStandaloneLessonRequest(draft.id, draft.owner_id, 0, "Plan"))
    saved = repository.require_by_id(LessonId(draft.id))
    assert saved.content.image == "generated-thumbnail"
    assert saved.content.plan is None
    assert saved.revision == 1
    agent.error = None
    result = planner.execute(
        ReviseStandaloneLessonRequest(draft.id, draft.owner_id, saved.revision, "Retry")
    )
    assert result.content.plan is not None
    assert len(generator.calls) == 1


def test_concurrent_edit_during_initial_thumbnail_is_preserved(standalone):
    repository, uow, agent, _, draft = standalone
    identifier = LessonId(draft.id)
    before = repository.require_by_id(identifier)

    def edit():
        repository.save(replace(before, description="Updated while drawing", revision=1))

    generator = RecordingThumbnails(uow, during=edit)
    planner = PlanStandaloneLesson(repository, uow, agent, thumbnails=generator)
    with pytest.raises(CourseConflict):
        planner.execute(ReviseStandaloneLessonRequest(draft.id, draft.owner_id, 0, "Plan"))
    saved = repository.require_by_id(identifier)
    assert saved.description == "Updated while drawing"
    assert saved.content.image == ""
    assert saved.content.plan is None
    assert not agent.calls


def test_generate_persists_draft_thumbnail_without_changing_its_content(standalone):
    repository, uow, _, _, draft = standalone
    before = repository.require_by_id(LessonId(draft.id))
    generator = RecordingThumbnails(uow)
    service = GenerateStandaloneThumbnail(repository, uow, generator)
    result = service.execute(ThumbnailRequest(draft.id, draft.owner_id))
    saved = repository.require_by_id(LessonId(draft.id))
    assert saved.content.image == result.content.image == "generated-thumbnail"
    assert saved.content == replace(before.content, image="generated-thumbnail")
    assert result.revision == draft.revision
    assert generator.calls == [(before.content.title, before.description, before.content.topics)]


def test_saved_thumbnail_is_reused_unless_explicitly_regenerated(standalone):
    repository, uow, _, _, draft = standalone
    generator = RecordingThumbnails(uow)
    service = GenerateStandaloneThumbnail(repository, uow, generator)
    first = service.execute(ThumbnailRequest(draft.id, draft.owner_id))
    cached = service.execute(ThumbnailRequest(draft.id, draft.owner_id))
    assert cached == first
    assert len(generator.calls) == 1
    regenerated = service.execute(ThumbnailRequest(draft.id, draft.owner_id, regenerate=True))
    assert regenerated.revision == first.revision
    assert len(generator.calls) == 2


def test_owner_is_checked_before_spending_on_generation(standalone):
    repository, uow, _, _, draft = standalone
    generator = RecordingThumbnails(uow)
    with pytest.raises(CourseNotFound):
        GenerateStandaloneThumbnail(repository, uow, generator).execute(
            ThumbnailRequest(draft.id, "another-owner")
        )
    assert not generator.calls


def test_generation_failure_keeps_existing_thumbnail_and_revision(standalone):
    repository, uow, _, _, draft = standalone
    before = repository.require_by_id(LessonId(draft.id))
    generator = RecordingThumbnails(uow, fail=True)
    with pytest.raises(ThumbnailUnavailable):
        GenerateStandaloneThumbnail(repository, uow, generator).execute(
            ThumbnailRequest(draft.id, draft.owner_id, regenerate=True)
        )
    assert repository.require_by_id(LessonId(draft.id)) == before


def test_concurrent_edit_is_preserved_instead_of_overwritten(standalone):
    repository, uow, _, _, draft = standalone
    identifier = LessonId(draft.id)
    before = repository.require_by_id(identifier)

    def edit():
        repository.save(replace(before, description="Edited while drawing", revision=1))

    generator = RecordingThumbnails(uow, during=edit)
    with pytest.raises(CourseConflict):
        GenerateStandaloneThumbnail(repository, uow, generator).execute(
            ThumbnailRequest(draft.id, draft.owner_id)
        )
    saved = repository.require_by_id(identifier)
    assert saved.description == "Edited while drawing"
    assert saved.content.image == ""


def test_thumbnail_finishing_during_outline_is_preserved(standalone):
    repository, uow, agent, planner, draft = standalone
    thumbnail = GenerateStandaloneThumbnail(repository, uow, RecordingThumbnails(uow))
    agent.during_run = lambda: thumbnail.execute(ThumbnailRequest(draft.id, draft.owner_id))

    result = planner.execute(ReviseStandaloneLessonRequest(draft.id, draft.owner_id, 0))

    saved = repository.require_by_id(LessonId(draft.id))
    assert saved.content.image == result.content.image == "generated-thumbnail"
    assert asdict(saved.content.plan) == asdict(result.content.plan)
    assert result.revision == 1


def test_outline_finishing_during_thumbnail_is_preserved(standalone):
    repository, uow, _, planner, draft = standalone
    generator = RecordingThumbnails(
        uow,
        during=lambda: planner.execute(ReviseStandaloneLessonRequest(draft.id, draft.owner_id, 0)),
    )

    result = GenerateStandaloneThumbnail(repository, uow, generator).execute(
        ThumbnailRequest(draft.id, draft.owner_id)
    )

    saved = repository.require_by_id(LessonId(draft.id))
    assert saved.content.image == result.content.image == "generated-thumbnail"
    assert asdict(saved.content.plan) == asdict(result.content.plan)
    assert saved.content.plan is not None
    assert result.revision == 1


@pytest.mark.parametrize(
    "style_id",
    [
        "flat-vector-science",
        "watercolor-wash",
        "tech-glow",
        "whiteboard",
        "halftone-pop",
        "risograph",
        "gouache-poster",
        "soft-3d",
        "memphis",
        "bauhaus",
        "swiss-grid",
    ],
)
@pytest.mark.parametrize("inline", [False, True])
def test_thumbnail_uses_selected_video_style_without_llm(standalone, style_id, inline):
    repository, uow, agent, _, draft = standalone
    identifier = LessonId(draft.id)
    before = repository.require_by_id(identifier)
    style = LessonStyle(visual_style_id=style_id, resolved=False)
    repository.save(replace(before, content=replace(before.content, style=style)))
    generator = RecordingThumbnails(uow)
    if inline:
        PlanStandaloneLesson(repository, uow, agent, thumbnails=generator).execute(
            ReviseStandaloneLessonRequest(draft.id, draft.owner_id, 0)
        )
    else:
        GenerateStandaloneThumbnail(repository, uow, generator).execute(
            ThumbnailRequest(draft.id, draft.owner_id)
        )
    assert generator.visual_directions == [VisualStyle(style.visual_style_id).direction()]
    assert repository.require_by_id(identifier).content.image == "generated-thumbnail"


def test_thumbnail_defaults_to_default_video_style(standalone):
    repository, uow, _, _, draft = standalone
    generator = RecordingThumbnails(uow)
    GenerateStandaloneThumbnail(repository, uow, generator).execute(
        ThumbnailRequest(draft.id, draft.owner_id)
    )
    assert generator.visual_directions == [VisualStyle().direction()]


def test_style_change_during_thumbnail_generation_discards_stale_image(standalone):
    repository, uow, _, _, draft = standalone
    identifier = LessonId(draft.id)
    before = repository.require_by_id(identifier)
    style = LessonStyle(visual_style_id="whiteboard")

    def restyle():
        repository.save(replace(before, content=replace(before.content, style=style)))

    generator = RecordingThumbnails(uow, during=restyle)
    with pytest.raises(CourseConflict):
        GenerateStandaloneThumbnail(repository, uow, generator).execute(
            ThumbnailRequest(draft.id, draft.owner_id)
        )
    saved = repository.require_by_id(identifier)
    assert saved.content.style == style
    assert saved.content.image == ""
    generator.during = None
    GenerateStandaloneThumbnail(repository, uow, generator).execute(
        ThumbnailRequest(draft.id, draft.owner_id, regenerate=True)
    )
    assert generator.visual_directions[-1] == VisualStyle(style.visual_style_id).direction()
    assert repository.require_by_id(identifier).content.image == "generated-thumbnail"


def test_style_resolution_during_thumbnail_does_not_discard_selected_preset(standalone):
    repository, uow, _, _, draft = standalone
    identifier = LessonId(draft.id)
    before = repository.require_by_id(identifier)
    selected = LessonStyle(visual_style_id="tech-glow", resolved=False)
    before = replace(before, content=replace(before.content, style=selected))
    repository.save(before)
    resolved = replace(
        selected, resolved=True, visuals="Diagrams for beginners", voice_id="narrator"
    )

    def finish_style_planning():
        repository.save(replace(before, content=replace(before.content, style=resolved)))

    generator = RecordingThumbnails(uow, during=finish_style_planning)
    GenerateStandaloneThumbnail(repository, uow, generator).execute(
        ThumbnailRequest(draft.id, draft.owner_id)
    )
    saved = repository.require_by_id(identifier)
    assert saved.content.style == resolved
    assert saved.content.image == "generated-thumbnail"
    assert generator.visual_directions == [VisualStyle("tech-glow").direction()]
