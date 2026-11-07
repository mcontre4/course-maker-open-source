from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.domain.animation import AnimationProject
from app.courses.ports.animator import AnimationInput, Animator


class CanvasProduction:
    def __init__(self, production: ProduceCanvasAnimation, animator: Animator) -> None:
        self._production, self._animator = production, animator

    def generate(self, request: AnimationInput) -> AnimationProject:
        return self._production.execute(ProduceCanvasAnimationRequest(request)).project

    def verify(self, project: AnimationProject) -> None:
        self._animator.verify(project)
