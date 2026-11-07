from typing import Annotated, Literal

from fastapi import Depends
from pydantic import ConfigDict, Field

from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.standalone import Owner, RevisionInput, StandaloneLessonView, router
from app.courses.application.outline_dto import (
    LessonOutlineInput,
    SaveStandaloneOutlineRequest,
    TeachingBeatInput,
    WorkedExampleInput,
)
from app.courses.application.save_standalone_outline import SaveStandaloneOutline

OutlineText = Annotated[str, Field(min_length=1, max_length=6000)]


class OutlineContentModel(HttpModel):
    model_config = ConfigDict(str_strip_whitespace=False)


class TeachingBeatEdit(OutlineContentModel):
    title: OutlineText
    purpose: OutlineText
    teaching_notes: OutlineText
    concepts: Annotated[tuple[OutlineText, ...], Field(min_length=1)]
    seconds: Annotated[int, Field(gt=0, strict=True)]
    check_question: Annotated[str, Field(max_length=6000)]
    expected_answer: Annotated[str, Field(max_length=6000)]


class WorkedExampleEdit(OutlineContentModel):
    problem: OutlineText
    steps: tuple[OutlineText, ...]
    result: OutlineText


class OutlineEdit(OutlineContentModel):
    objectives: Annotated[tuple[OutlineText, ...], Field(min_length=1)]
    assumed_knowledge: tuple[OutlineText, ...]
    introduced_knowledge: Annotated[tuple[OutlineText, ...], Field(min_length=1)]
    beats: Annotated[tuple[TeachingBeatEdit, ...], Field(min_length=1, max_length=30)]
    required_facts: Annotated[tuple[OutlineText, ...], Field(min_length=1)]
    equations: tuple[OutlineText, ...]
    examples: Annotated[tuple[WorkedExampleEdit, ...], Field(min_length=1)]
    misconceptions: tuple[OutlineText, ...]
    scope_boundaries: Annotated[tuple[OutlineText, ...], Field(min_length=1)]
    feasibility_status: Literal["feasible", "infeasible"] | None = None
    feasibility_explanation: Annotated[str, Field(max_length=6000)] = ""
    recommended_video_minutes: Annotated[int, Field(ge=1, le=1440, strict=True)] | None = None
    recommended_scope_adjustment: Annotated[str, Field(max_length=6000)] = ""

    def to_input(self) -> LessonOutlineInput:
        return LessonOutlineInput(
            objectives=self.objectives,
            assumed_knowledge=self.assumed_knowledge,
            introduced_knowledge=self.introduced_knowledge,
            beats=tuple(TeachingBeatInput(**beat.model_dump()) for beat in self.beats),
            required_facts=self.required_facts,
            equations=self.equations,
            examples=tuple(WorkedExampleInput(**example.model_dump()) for example in self.examples),
            misconceptions=self.misconceptions,
            scope_boundaries=self.scope_boundaries,
            feasibility_status=self.feasibility_status,
            feasibility_explanation=self.feasibility_explanation,
            recommended_video_minutes=self.recommended_video_minutes,
            recommended_scope_adjustment=self.recommended_scope_adjustment,
        )


class SaveOutlineInput(RevisionInput):
    outline: OutlineEdit


def get_save_outline() -> SaveStandaloneOutline:
    raise RuntimeError("Standalone lessons are not configured")


@router.put("/{lesson_id}/outline", response_model=StandaloneLessonView)
def save_outline(
    lesson_id: str,
    payload: SaveOutlineInput,
    owner: Owner,
    service: Annotated[SaveStandaloneOutline, Depends(get_save_outline)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            SaveStandaloneOutlineRequest(
                lesson_id, owner, payload.expected_revision, payload.outline.to_input()
            )
        )
    )
