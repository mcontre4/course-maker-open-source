from dataclasses import dataclass, replace

from app.courses.domain.animation import AnimationProject
from app.courses.ports.animator import AnimationInput, AnimationUnavailable, Animator
from app.courses.ports.visual_production import AnimationReviewer, VisualAssetGenerator


@dataclass(frozen=True)
class ProduceIllustratedAnimationRequest:
    animation: AnimationInput


@dataclass(frozen=True)
class ProduceIllustratedAnimationResponse:
    project: AnimationProject


class ProduceIllustratedAnimation:
    """Only return a lesson after its generated illustrations and rendered review succeed."""

    def __init__(
        self, assets: VisualAssetGenerator, animator: Animator, reviewer: AnimationReviewer
    ) -> None:
        self._assets, self._animator, self._reviewer = assets, animator, reviewer

    def execute(
        self, request: ProduceIllustratedAnimationRequest
    ) -> ProduceIllustratedAnimationResponse:
        assets = self._assets.generate(request.animation)
        animation = replace(
            request.animation,
            asset_project_key=assets.project_key,
            asset_output_hash=assets.output_hash,
        )
        for attempt in range(2):
            project = self._animator.generate(animation)
            review = self._reviewer.review(project)
            if review.approved:
                return ProduceIllustratedAnimationResponse(project)
            if attempt == 1:
                break
            if review.repair_target == "assets":
                assets = self._assets.generate(replace(animation, visual_feedback=review.feedback))
            animation = replace(
                animation,
                asset_project_key=assets.project_key,
                asset_output_hash=assets.output_hash,
                visual_feedback=review.feedback,
                previous_project_key=project.project_key,
            )
        raise AnimationUnavailable("Visual review failed after repair: " + review.feedback[:2000])
