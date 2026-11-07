from dataclasses import replace

import pytest

pytestmark = pytest.mark.integration


def test_explicit_regeneration_bypasses_animation_cache_and_preserves_original(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    original = animator.generate(inputs)
    original_source = (root / original.project_key / "animation.js").read_bytes()
    assert animator.generate(inputs) == original
    assert commands.authoring_round == 1

    restart = replace(inputs, regeneration_key="lesson-revision-7")
    regenerated = animator.generate(restart)
    assert regenerated.project_key != original.project_key
    assert commands.authoring_round == 2
    assert (root / original.project_key / "animation.js").read_bytes() == original_source
    assert animator.generate(restart) == regenerated
    assert commands.authoring_round == 2
