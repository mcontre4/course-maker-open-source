from dataclasses import asdict

from app.courses.application.lesson_plan_dto import LessonPlanResponse
from app.courses.application.outline_dto import (
    LessonOutlineInput,
    TeachingBeatInput,
    WorkedExampleInput,
)


def outline_input(plan: LessonPlanResponse) -> LessonOutlineInput:
    return LessonOutlineInput(
        objectives=plan.objectives,
        assumed_knowledge=plan.assumed_knowledge,
        introduced_knowledge=plan.introduced_knowledge,
        beats=tuple(TeachingBeatInput(**asdict(beat)) for beat in plan.beats),
        required_facts=plan.required_facts,
        equations=plan.equations,
        examples=tuple(WorkedExampleInput(**asdict(example)) for example in plan.examples),
        misconceptions=plan.misconceptions,
        scope_boundaries=plan.scope_boundaries,
        feasibility_status=plan.feasibility_status,
        feasibility_explanation=plan.feasibility_explanation,
        recommended_video_minutes=plan.recommended_video_minutes,
        recommended_scope_adjustment=plan.recommended_scope_adjustment,
    )
