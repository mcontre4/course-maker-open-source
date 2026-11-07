from dataclasses import replace

import pytest
from fakes.animation_elements import RecordingElementAgent
from fakes.canvas import RecordingDelivery
from fakes.visual_production import RecordingCompositor
from fixtures.animation import animation_inputs

from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.ports.visual_production import VisualReview


@pytest.mark.parametrize("enabled", [False, True])
def test_element_preparation_is_opt_in_and_repair_reuses_editable_sources(enabled):
    inputs, _, _, _ = animation_inputs()
    events = []
    elements = RecordingElementAgent(events)
    animator, delivery = RecordingCompositor(events), RecordingDelivery()
    delivery.decisions = [VisualReview(False, "Adapt artwork"), VisualReview(True, "Valid")]
    ProduceCanvasAnimation(animator, delivery, elements).execute(
        ProduceCanvasAnimationRequest(replace(inputs, prepare_elements=enabled))
    )
    assert events == (["elements"] if enabled else []) + [
        "animation",
        "animation",
    ]
    assert len(elements.requests) == int(enabled)
    first, repair = animator.requests
    assert bool(first.prepared_elements) is enabled
    assert first.prepared_elements == repair.prepared_elements
    assert first.storyboard == inputs.storyboard
    assert first.audio == inputs.audio


@pytest.mark.parametrize("original,selected", [(False, True), (True, False), (True, True)])
def test_existing_source_respects_preparation_flag(original, selected):
    inputs, _, _, _ = animation_inputs()
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    source = replace(animator.generate(inputs), prepare_elements=original)
    animator.requests.clear()
    elements = RecordingElementAgent([])
    ProduceCanvasAnimation(animator, delivery, elements).execute(
        ProduceCanvasAnimationRequest(
            replace(inputs, prepare_elements=selected, existing_project=source)
        )
    )
    changed = original != selected
    assert len(animator.requests) == int(changed)
    assert len(elements.requests) == int(changed and selected)
