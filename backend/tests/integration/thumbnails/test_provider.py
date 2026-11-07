import base64
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pytest

from app.courses.adapters.ai.thumbnails import OpenRouterThumbnails, svg_image_reference
from app.courses.ports.thumbnails import ThumbnailUnavailable

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("name", ["inertia", "history", "math"])
def test_approved_references_survive_svg_validation(name):
    path = (
        Path(__file__).parents[3] / "src/app/courses/adapters/ai/thumbnail_examples" / f"{name}.svg"
    )
    reference = svg_image_reference(
        '<?xml version="1.0"?>\n<!-- illustration -->' + path.read_text()
    )
    document = base64.b64decode(reference.split(",", 1)[1])
    assert document.startswith(b"<svg")
    assert ET.fromstring(document).get("viewBox") == "0 0 640 400"


def test_provider_generates_svg_with_fixed_model_and_subject_context(thumbnail_server):
    with thumbnail_server() as (url, calls), httpx.Client(base_url=url) as client:
        reference = OpenRouterThumbnails(
            client, "test-key", "fast-svg-model", "Fixed art direction"
        ).generate("Inertia", "Newton's first law", ("Velocity",))
    svg = ET.fromstring(base64.b64decode(reference.split(",", 1)[1]))
    assert svg.get("viewBox") == "0 0 640 400"
    path, body = calls[0]
    assert path == "/api/v1/chat/completions"
    assert body["model"] == "fast-svg-model"
    assert body["reasoning"] == {"effort": "medium"}
    assert body["messages"][0]["content"] == "Fixed art direction"
    assert "Inertia" in body["messages"][1]["content"]


@pytest.mark.parametrize(
    "content",
    [
        "<script>alert(1)</script>",
        "<foreignObject><div>HTML</div></foreignObject>",
        '<image href="https://example.com/track"/>',
        '<rect width="100" height="100" onload="alert(1)"/>',
        '<rect width="100" height="100" style="fill:red"/>',
        '<rect width="100" height="100" fill="url(https://example.com/image)"/>',
        '<rect width="100" height="100" fill="#not-a-color"/>',
    ],
)
def test_untrusted_svg_is_rejected(thumbnail_server, content):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400">{content}</svg>'
    with thumbnail_server(svg) as (url, _), httpx.Client(base_url=url) as client:
        with pytest.raises(ThumbnailUnavailable):
            OpenRouterThumbnails(client, "key", "model", "brief").generate(
                "Topic", "Description", ()
            )


@pytest.mark.parametrize(
    "status,finish,svg",
    [
        (503, "stop", None),
        (200, "length", None),
        (200, "stop", "not SVG"),
        (200, "stop", '<!DOCTYPE svg [<!ENTITY x "x">]><svg/>'),
        (200, "stop", "x" * 40001),
    ],
)
def test_provider_and_invalid_output_failures_are_explicit(thumbnail_server, status, finish, svg):
    with thumbnail_server(svg, status, finish) as (url, _), httpx.Client(base_url=url) as client:
        with pytest.raises(ThumbnailUnavailable):
            OpenRouterThumbnails(client, "key", "model", "brief").generate(
                "Topic", "Description", ()
            )


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [None]},
        {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": []}}]},
    ],
)
def test_malformed_provider_envelopes_become_retryable_errors(thumbnail_server, body):
    with thumbnail_server(response_body=body) as (url, _), httpx.Client(base_url=url) as client:
        with pytest.raises(ThumbnailUnavailable):
            OpenRouterThumbnails(client, "key", "model", "brief").generate(
                "Topic", "Description", ()
            )


@pytest.mark.parametrize("color", ["#070B24", "#00E5FF", "#FFFFFF", "#FF0000", "#FE3"])
def test_provider_passes_video_direction_and_accepts_style_colors(thumbnail_server, color):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400">'
        f'<rect width="640" height="400" fill="{color}"/></svg>'
    )
    direction = "Tech Glow: deep navy background with electric cyan glow"
    with thumbnail_server(svg) as (url, calls), httpx.Client(base_url=url) as client:
        reference = OpenRouterThumbnails(client, "test-key", "model", "brief").generate(
            "Inertia", "Newton's first law", ("Velocity",), visual_direction=direction
        )
    content = json.loads(calls[0][1]["messages"][1]["content"])
    assert content == {
        "title": "Inertia",
        "description": "Newton's first law",
        "topics": ["Velocity"],
        "visual_direction": direction,
    }
    document = ET.fromstring(base64.b64decode(reference.split(",", 1)[1]))
    assert document[0].get("fill") == color
