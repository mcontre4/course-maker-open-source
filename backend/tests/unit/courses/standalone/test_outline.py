from dataclasses import replace

import pytest
from fakes.animator import RecordingAnimator
from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fakes.storyboard_agent import RecordingStoryboardAgent
from fixtures.outline import outline_input

from app.courses.application.outline_dto import SaveStandaloneOutlineRequest
from app.courses.application.save_standalone_outline import SaveStandaloneOutline
from app.courses.application.standalone import ApproveStandaloneLesson
from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.speech import SpeechSettings

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"


def test_direct_edit_flows_to_all_media_in_fast_mode_without_replanning(standalone):
    repo, uow, agent, planner, created = standalone
    planned = planner.execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan", GenerationMode.FAST)
    )
    assert planned.content.plan is not None
    outline = outline_input(planned.content.plan)
    outline = replace(
        outline,
        objectives=("Explain sharing electrons in water",),
        beats=(replace(outline.beats[0], teaching_notes="Use two hydrogen atoms and one oxygen."),),
        examples=(replace(outline.examples[0], problem="How does water form?"),),
    )
    saved = SaveStandaloneOutline(repo, uow).execute(
        SaveStandaloneOutlineRequest(created.id, OWNER, planned.revision, outline)
    )
    assert saved.content.plan is not None
    assert saved.content.plan.objectives == outline.objectives
    assert saved.content.plan.beats[0].teaching_notes == outline.beats[0].teaching_notes
    assert saved.content.plan.examples[0].problem == "How does water form?"
    assert saved.content.plan.sources == planned.content.plan.sources
    assert saved.turns == planned.turns
    assert not saved.approved

    def request(revision):
        return ReviseStandaloneLessonRequest(
            created.id, OWNER, revision, generation_mode=GenerationMode.FAST
        )

    approved = ApproveStandaloneLesson(repo, uow).execute(request(saved.revision))
    board_agent = RecordingStoryboardAgent(uow)
    board = GenerateStandaloneStoryboard(repo, uow, board_agent).execute(request(approved.revision))
    assert board_agent.calls[0].plan == repo.require_by_id(LessonId(created.id)).content.plan
    assert board_agent.calls[0].generation_mode is GenerationMode.FAST
    artifacts = InMemorySpeechArtifacts(uow)
    voiced = GenerateStandaloneSpeech(
        repo, uow, RecordingSpeech(uow), artifacts, SpeechSettings("test-voice")
    ).execute(request(board.revision))
    animator = RecordingAnimator(uow)
    animated = GenerateStandaloneAnimation(repo, uow, animator, artifacts).execute(
        request(voiced.revision)
    )
    assert animated.content.animation is not None
    assert animator.calls[0].generation_mode is GenerationMode.FAST
    assert animator.calls[0].plan == board_agent.calls[0].plan
    assert len(agent.calls) == 1
    reset = SaveStandaloneOutline(repo, uow).execute(
        SaveStandaloneOutlineRequest(
            created.id,
            OWNER,
            animated.revision,
            replace(outline, required_facts=("Water contains hydrogen and oxygen",)),
        )
    )
    assert reset.content.storyboard is None
    assert reset.content.alignment is None
    assert reset.content.animation is None
    assert not reset.approved
    assert repo.require_by_id(LessonId(created.id)).revision == reset.revision
    # An explicit chat request subsequently starts from the edited plan and objectives.
    edited_plan = repo.require_by_id(LessonId(created.id)).content.plan
    planner.execute(replace(request(reset.revision), message="Refine my saved edits"))
    assert agent.calls[-1].previous_plan == edited_plan
    assert agent.calls[-1].brief.objectives == outline.objectives


def test_noop_save_preserves_approval_and_revision(standalone):
    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    approved = ApproveStandaloneLesson(repo, uow).execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, planned.revision)
    )
    result = SaveStandaloneOutline(repo, uow).execute(
        SaveStandaloneOutlineRequest(
            created.id, OWNER, approved.revision, outline_input(approved.content.plan)
        )
    )
    assert result == approved


@pytest.mark.parametrize("failure", ["owner", "stale", "timing", "coverage", "objectives"])
def test_invalid_edit_preserves_saved_plan(standalone, failure):
    repo, uow, agent, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    original = repo.require_by_id(LessonId(created.id))
    outline = outline_input(planned.content.plan)
    if failure == "timing":
        outline = replace(outline, beats=(replace(outline.beats[0], seconds=300),))
    if failure == "coverage":
        outline = replace(outline, beats=(replace(outline.beats[0], concepts=("Other",)),))
    if failure == "objectives":
        outline = replace(outline, objectives=("a" * 201,))
    expected = (
        CourseNotFound
        if failure == "owner"
        else (CourseConflict if failure == "stale" else CourseError)
    )
    with pytest.raises(expected):
        SaveStandaloneOutline(repo, uow).execute(
            SaveStandaloneOutlineRequest(
                created.id,
                OTHER if failure == "owner" else OWNER,
                0 if failure == "stale" else planned.revision,
                outline,
            )
        )
    assert repo.require_by_id(LessonId(created.id)) == original
    assert len(agent.calls) == 1


def test_draft_without_plan_cannot_be_edited(standalone):
    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    saved = repo.require_by_id(LessonId(created.id))
    repo.save(replace(saved, content=replace(saved.content, plan=None)))
    with pytest.raises(CourseConflict, match="Generate"):
        SaveStandaloneOutline(repo, uow).execute(
            SaveStandaloneOutlineRequest(
                created.id, OWNER, saved.revision, outline_input(planned.content.plan)
            )
        )
