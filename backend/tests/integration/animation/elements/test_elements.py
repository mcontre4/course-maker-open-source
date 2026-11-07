import json
from dataclasses import replace

import pytest

from app.courses.ports.animator import AnimationUnavailable

pytestmark = pytest.mark.integration


def test_single_agent_identifies_and_generates_ten_parallel_elements_in_selected_style(
    element_runtime,
):
    agent, provider, author, author_provider, inputs, root = element_runtime
    scope = provider.scope.set("lesson-usage-scope")
    try:
        elements = agent.generate(inputs)
    finally:
        provider.scope.reset(scope)
    assert len(elements) == 10
    assert [e.spec.id for e in elements] == [f"car_{i}" for i in range(10)]
    assert provider.scopes == ["lesson-usage-scope"] * 11
    assert all(r["max_tokens"] == 16000 for r in provider.requests)
    assert len({r["messages"][0]["content"] for r in provider.requests}) == 1
    for request in provider.requests:
        context = json.loads(request["messages"][-1]["content"][0]["text"])
        assert context["visual_style"] == inputs.visual_style
        assert set(context["style"]) == {"STYLE.md", "drawing.js"}
    assert agent.generate(inputs) == elements
    assert len(provider.requests) == 11

    author_provider.outputs = [
        "window.explainer=(ctx,W,H,t)=>{FV.sky(ctx,W,H,t);};"
        "window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];"
        "// Animator adapted the supplied car artwork"
    ]
    project = author.generate(replace(inputs, prepare_elements=True, prepared_elements=elements))
    supplied = author_provider.requests[0]["messages"][-1]["content"][0]["text"]
    assert "prepared_elements" in supplied
    assert "draw_car_9" in supplied
    system = author_provider.requests[0]["messages"][0]["content"]
    assert "edit shapes" in system
    assert project.prepare_elements is True
    saved = json.loads((root / project.input_hash / "inputs.json").read_text())
    assert len(saved["prepared_elements"]) == 10
    assert "adapted" in (root / project.project_key / "animation.js").read_text()


def test_invalid_plan_is_rejected_before_any_element_generation(element_runtime):
    agent, provider, _, _, inputs, _ = element_runtime
    provider.invalid_plan = True
    with pytest.raises(AnimationUnavailable, match="invalid element list"):
        agent.generate(inputs)
    provider.invalid_plan = False
    assert len(agent.generate(inputs)) == 10
    assert len(provider.requests) == 12


def test_invalid_element_source_is_not_saved_as_a_successful_cache_entry(element_runtime):
    agent, provider, _, _, inputs, _ = element_runtime
    provider.invalid_source = True
    with pytest.raises(AnimationUnavailable, match="missing its drawing function"):
        agent.generate(inputs)
    assert len(provider.requests) == 11


def test_retry_only_regenerates_the_failed_element(element_runtime):
    agent, provider, _, _, inputs, _ = element_runtime
    provider.invalid_element_ids = {"car_9"}
    with pytest.raises(AnimationUnavailable, match="missing its drawing function"):
        agent.generate(inputs)
    provider.invalid_element_ids.clear()
    provider.barrier = None
    assert len(agent.generate(inputs)) == 10
    assert len(provider.requests) == 12  # One plan, ten original calls, one retry.


@pytest.mark.parametrize("damage", ["invalid_json", "checksum_mismatch"])
def test_corrupt_cache_is_replaced_without_repeating_successful_calls(element_runtime, damage):
    agent, provider, _, _, inputs, root = element_runtime
    elements = agent.generate(inputs)
    for path in (root / ".elements").glob("*/result.json"):
        cached = json.loads(path.read_text())
        if "function draw_car_9" in cached["output"]:
            if damage == "invalid_json":
                path.write_text("{")
            else:
                path.write_text(json.dumps({**cached, "output": cached["output"] + "// corrupt"}))
            break
    else:
        pytest.fail("Expected cached car_9 source")
    provider.barrier = None
    assert agent.generate(inputs) == elements
    assert len(provider.requests) == 12


def test_missing_style_files_raise_an_application_error(element_runtime):
    agent, _, _, _, inputs, _ = element_runtime
    with pytest.raises(AnimationUnavailable, match="could not read or save its files"):
        agent.generate(replace(inputs, visual_style_id="missing-style"))
