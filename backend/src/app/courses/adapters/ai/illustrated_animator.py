from app.courses.application.produce_illustrated_animation import (
    ProduceIllustratedAnimation,
    ProduceIllustratedAnimationRequest,
)
from app.courses.domain.animation import AnimationProject
from app.courses.ports.animator import AnimationInput, Animator


class IllustratedAnimator:
    def __init__(self, production: ProduceIllustratedAnimation, animator: Animator) -> None:
        self._production, self._animator = production, animator

    def generate(self, request: AnimationInput) -> AnimationProject:
        return self._production.execute(ProduceIllustratedAnimationRequest(request)).project

    def verify(self, project: AnimationProject) -> None:
        self._animator.verify(project)
