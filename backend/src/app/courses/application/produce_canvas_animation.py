import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

from app.courses.domain.animation import AnimationProject
from app.courses.ports.animation_delivery import AnimationDelivery
from app.courses.ports.animation_elements import AnimationElementAgent
from app.courses.ports.animator import (
    AnimationInput,
    AnimationUnavailable,
    Animator,
    StoryboardChangeRequired,
)


@dataclass(frozen=True)
class ProduceCanvasAnimationRequest:
    animation: AnimationInput


@dataclass(frozen=True)
class ProduceCanvasAnimationResponse:
    project: AnimationProject


class ProduceCanvasAnimation:
    def __init__(
        self,
        animator: Animator,
        delivery: AnimationDelivery,
        element_agent: AnimationElementAgent | None = None,
    ) -> None:
        self._animator, self._delivery = animator, delivery
        self._element_agent = element_agent

    def execute(self, request: ProduceCanvasAnimationRequest) -> ProduceCanvasAnimationResponse:
        animation = request.animation
        if animation.existing_project is not None and (
            animation.existing_project.backend != animation.animation_backend.value
            or animation.existing_project.prepare_elements != animation.prepare_elements
            or (
                animation.animator_model is not None
                and animation.existing_project.model != animation.animator_model.value
            )
        ):
            animation = replace(animation, existing_project=None)
        if animation.existing_project is not None:
            project = animation.existing_project
            self._animator.verify(project)
        else:
            if animation.prepare_elements and not animation.prepared_elements:
                if self._element_agent is None:
                    raise AnimationUnavailable("Element preparation is not configured")
                animation = replace(
                    animation, prepared_elements=self._element_agent.generate(animation)
                )
            project = self._animator.generate(animation)
        if animation.session:
            same_scope = project.owner_id in (None, animation.session.owner_id) and (
                animation.session.job_id is None or animation.session.job_id == project.job_id
            )
            project = replace(
                project,
                owner_id=animation.session.owner_id,
                job_id=animation.session.job_id or project.job_id,
                session_id=project.session_id if same_scope else None,
                reviewer_session_id=animation.reviewer_session_id,
            )
        try:
            decision = self._delivery.deliver(
                project,
                review=animation.review_output,
                source_ready=self._source_ready(animation, project),
            )
        except (AnimationUnavailable, StoryboardChangeRequired) as exc:
            if not animation.review_output:
                raise
            return ProduceCanvasAnimationResponse(
                self._deliver_with_warning(animation, project, str(exc))
            )
        status = "approved" if animation.review_output else "skipped"
        project = replace(
            project, reviewer_session_id=decision.session_id or project.reviewer_session_id
        )
        if not decision.approved:
            if not animation.review_output:
                raise AnimationUnavailable(
                    "Video technical validation failed: " + decision.feedback
                )
            logging.getLogger(__name__).warning(
                "Visual review suggestions for lesson %s: %s", project.lesson_id, decision.feedback
            )
            original = project
            try:
                project = self._animator.generate(
                    replace(
                        animation,
                        visual_feedback=decision.feedback,
                        previous_project_key=project.project_key,
                        existing_project=None,
                        session=replace(animation.session, session_id=project.session_id)
                        if animation.session and project.session_id
                        else animation.session,
                    )
                )
                project = replace(project, reviewer_session_id=original.reviewer_session_id)
                # One visual review and one optional repair, followed by technical verification.
                verified = self._delivery.deliver(
                    project,
                    review=False,
                    repair_feedback=decision.feedback,
                    source_ready=self._source_ready(animation, project),
                )
                if not verified.approved:
                    raise AnimationUnavailable(
                        "Video validation failed after repair: " + verified.feedback
                    )
            except (AnimationUnavailable, StoryboardChangeRequired) as exc:
                return ProduceCanvasAnimationResponse(
                    self._deliver_with_warning(
                        animation, original, f"{decision.feedback}; repair: {exc}"
                    )
                )
            status = "repaired"
        return ProduceCanvasAnimationResponse(replace(project, review_status=status))

    def _source_ready(
        self, animation: AnimationInput, project: AnimationProject
    ) -> Callable[[], None]:
        def announce() -> None:
            if animation.source_ready is not None:
                # Source is final; delivery remains pending until encoding completes.
                animation.source_ready(replace(project, review_status="pending"))

        return announce

    def _deliver_with_warning(
        self, animation: AnimationInput, project: AnimationProject, warning: str
    ) -> AnimationProject:
        logging.getLogger(__name__).warning(
            "Visual review is non-blocking for lesson %s; rendering existing source: %s",
            project.lesson_id,
            warning,
        )
        verified = self._delivery.deliver(
            project, review=False, source_ready=self._source_ready(animation, project)
        )
        if not verified.approved:
            raise AnimationUnavailable("Video technical validation failed: " + verified.feedback)
        return replace(project, review_status="warning")
