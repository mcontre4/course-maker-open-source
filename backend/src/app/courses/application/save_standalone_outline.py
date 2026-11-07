from dataclasses import replace

from app.courses.application.outline_dto import LessonOutlineInput, SaveStandaloneOutlineRequest
from app.courses.application.standalone import _StandaloneUseCase
from app.courses.application.standalone_dto import StandaloneLessonResponse, standalone_response
from app.courses.domain.errors import CourseConflict
from app.courses.domain.lesson_plan import LessonPlan, TeachingBeat, WorkedExample


class SaveStandaloneOutline(_StandaloneUseCase):
    def execute(self, request: SaveStandaloneOutlineRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id, lock=True)
            before.require_revision(request.expected_revision)
            if before.content.plan is None:
                raise CourseConflict("Generate a lesson outline before editing it")
            outline = request.outline
            assessment: LessonOutlineInput | LessonPlan = outline
            if outline.feasibility_status is None and not (
                outline.feasibility_explanation
                or outline.recommended_video_minutes is not None
                or outline.recommended_scope_adjustment
            ):
                # Older clients omit assessment fields; they must not erase a saved decision.
                assessment = before.content.plan
            plan = LessonPlan(
                lesson_id=str(before.content.id),
                objectives=outline.objectives,
                assumed_knowledge=outline.assumed_knowledge,
                introduced_knowledge=outline.introduced_knowledge,
                beats=tuple(
                    TeachingBeat(
                        beat.title,
                        beat.purpose,
                        beat.teaching_notes,
                        beat.concepts,
                        beat.seconds,
                        beat.check_question,
                        beat.expected_answer,
                    )
                    for beat in outline.beats
                ),
                required_facts=outline.required_facts,
                equations=outline.equations,
                examples=tuple(
                    WorkedExample(example.problem, example.steps, example.result)
                    for example in outline.examples
                ),
                misconceptions=outline.misconceptions,
                scope_boundaries=outline.scope_boundaries,
                sources=before.content.plan.sources,
                feasibility_status=assessment.feasibility_status,
                feasibility_explanation=assessment.feasibility_explanation,
                recommended_video_minutes=assessment.recommended_video_minutes,
                recommended_scope_adjustment=assessment.recommended_scope_adjustment,
            )
            if plan.feasibility_status == "infeasible":
                plan = replace(plan, recommended_video_minutes=plan.minimum_video_minutes)
            updated = before.edit_outline(plan)
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)
