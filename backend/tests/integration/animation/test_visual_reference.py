import json
import shutil
from pathlib import Path

import pytest

from app.courses.adapters.ai.visual_reference import (
    preferred_style_example,
    select_teaching_example,
    teaching_example_identity,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "manifest",
    [{"examples": ["examples/missing.js"]}, {"examples": "examples/reference.js"}],
)
def test_invalid_preferred_example_does_not_silently_fall_back(tmp_path, manifest):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "reference.js").write_text("// Available but not the curated choice")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="example"):
        preferred_style_example(tmp_path)


@pytest.mark.parametrize(
    "speech,pattern",
    [
        ("Trace the light ray and shadow.", "mechanism"),
        ("Compare the difference using the same baseline.", "comparison"),
        ("Solve this equation and divide both sides.", "worked-example"),
        ("Select the file, click save, then open the folder.", "procedure"),
        ("Trade routes connected cities through intermediaries and local exchange.", "network"),
        (
            "Military powers restricted Congress and rights before a gradual civilian transition.",
            "institutional-change",
        ),
        (
            "A ditadura ampliou a censura e restringiu direitos durante a transicao.",
            "institutional-change",
        ),
        ("Uma rede de rotas ligou o comercio e as conexoes entre cidades.", "network"),
        ("Unfamiliar vocabulary without a catalog match.", "mechanism"),
    ],
)
def test_reference_matches_explanation_and_is_stable_across_stages(speech, pattern):
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    segment = {"narration_text": speech, "learning_purpose": "", "equations": []}
    before = select_teaching_example(tools, "flat-vector-science", {"segments": [segment]})
    after = select_teaching_example(tools, "flat-vector-science", {"scenes": [segment]})
    assert before == after and before.id == pattern
    assert before.image.read_bytes().startswith(b"\x89PNG")
    assert "window.explainer" in before.source.read_text()
    assert json.loads(before.notes)["narration_and_visual_sequence"]


def test_equations_prioritize_worked_example_over_incidental_topic_words():
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    example = select_teaching_example(
        tools,
        "whiteboard",
        {
            "scenes": [
                {
                    "narration_text": "Compare trade routes between cities.",
                    "equations": ["2x + 3 = 11"],
                }
            ]
        },
    )
    assert example.id == "worked-example"


def test_reference_edits_invalidate_authoring_identity(tmp_path):
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    shutil.copytree(tools / "teaching-examples", tmp_path / "teaching-examples")
    before = teaching_example_identity(tmp_path)
    notes = tmp_path / "teaching-examples/network.json"
    notes.write_text(notes.read_text().replace("Silk Roads", "Silk Roads revised"))
    assert teaching_example_identity(tmp_path) != before


@pytest.mark.parametrize("resource", ["../outside.js", "/tmp/outside.js", "missing.js"])
def test_invalid_teaching_resources_fail_before_generation(tmp_path, resource):
    root = tmp_path / "teaching-examples"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "default": "mechanism",
                "examples": [
                    {
                        "id": "mechanism",
                        "source": resource,
                    }
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="Invalid teaching example"):
        select_teaching_example(tmp_path, "whiteboard", {"scenes": []})
