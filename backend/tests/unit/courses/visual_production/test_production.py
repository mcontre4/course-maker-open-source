import pytest

from app.courses.ports.animator import AnimationUnavailable
from app.courses.ports.visual_production import VisualReview


def test_only_returns_after_assets_composition_and_rendered_review(visual_production):
    service, request, events, assets, animator, reviewer = visual_production
    result = service.execute(request)
    assert events == ["assets", "animation", "review"]
    assert result.project == reviewer.projects[0]
    assert animator.requests[0].asset_output_hash == "b" * 64
    assert animator.requests[0].audio == request.animation.audio
    assert animator.requests[0].alignment == request.animation.alignment


def test_repairs_rejected_composition_without_regenerating_assets_or_audio(visual_production):
    service, request, events, assets, animator, reviewer = visual_production
    reviewer.decisions = [
        VisualReview(False, "s01 label overlaps the pump"),
        VisualReview(True, "Fixed"),
    ]
    service.execute(request)
    assert events == ["assets", "animation", "review", "animation", "review"]
    assert len(assets.requests) == 1
    assert animator.requests[1].visual_feedback == "s01 label overlaps the pump"
    assert animator.requests[1].previous_project_key == reviewer.projects[0].project_key
    assert animator.requests[1].audio == request.animation.audio


@pytest.mark.parametrize("target,asset_calls", [("animation", 1), ("assets", 2)])
def test_never_accepts_repeated_visual_failures(visual_production, target, asset_calls):
    service, request, events, assets, animator, reviewer = visual_production
    reviewer.decisions = [VisualReview(False, "Malformed object", target)] * 2
    with pytest.raises(AnimationUnavailable, match="Visual review failed.*Malformed object"):
        service.execute(request)
    assert len(animator.requests) == 2
    assert len(assets.requests) == asset_calls


def test_routes_artwork_defects_back_to_asset_production(visual_production):
    service, request, events, assets, _, reviewer = visual_production
    reviewer.decisions = [
        VisualReview(False, "Rod disconnects", "assets"),
        VisualReview(True, "Fixed"),
    ]
    service.execute(request)
    assert events == ["assets", "animation", "review", "assets", "animation", "review"]
    assert assets.requests[1].visual_feedback == "Rod disconnects"
    assert assets.requests[1].alignment == request.animation.alignment
