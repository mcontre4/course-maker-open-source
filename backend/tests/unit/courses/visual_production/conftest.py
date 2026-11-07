import pytest
from fakes.visual_production import (
    RecordingCompositor,
    RecordingVisualAssets,
    RecordingVisualReview,
)
from fixtures.animation import animation_inputs

from app.courses.application.produce_illustrated_animation import (
    ProduceIllustratedAnimation,
    ProduceIllustratedAnimationRequest,
)


@pytest.fixture
def visual_production():
    inputs, _, _, _ = animation_inputs()
    events = []
    assets = RecordingVisualAssets(events)
    animator = RecordingCompositor(events)
    reviewer = RecordingVisualReview(events)
    service = ProduceIllustratedAnimation(assets, animator, reviewer)
    return service, ProduceIllustratedAnimationRequest(inputs), events, assets, animator, reviewer
