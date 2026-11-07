import base64
import json
import re
from xml.etree import ElementTree as ET

import httpx

from app.courses.ports.thumbnails import ThumbnailUnavailable

_NS = "http://www.w3.org/2000/svg"
_TAGS = frozenset(
    "svg g path rect circle ellipse line polyline polygon defs clipPath linearGradient "
    "radialGradient stop pattern title desc".split()
)
_ATTRIBUTES = frozenset(
    "id viewBox width height x y x1 y1 x2 y2 cx cy r rx ry d points fill stroke stroke-width "
    "stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset stroke-miterlimit "
    "fill-rule clip-rule opacity fill-opacity stroke-opacity transform clip-path "
    "gradientUnits gradientTransform offset stop-color stop-opacity patternUnits "
    "patternTransform fx fy fr preserveAspectRatio role aria-labelledby".split()
)


def svg_image_reference(raw: str) -> str:
    """Fail closed on active content and external resources, then serialize a clean image."""
    raw = raw.strip()
    if raw.startswith("```svg") and raw.endswith("```"):
        raw = raw[6:-3].strip()
    if len(raw.encode()) > 40000:
        raise ValueError("SVG size limit exceeded")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    raw = re.sub(r"^<\?xml\s[^?]*\?>", "", raw).strip()
    if "<!" in raw or "<?" in raw:
        raise ValueError("Invalid SVG document")
    root = ET.fromstring(raw)
    if root.tag != f"{{{_NS}}}svg" or root.get("viewBox") != "0 0 640 400":
        raise ValueError("Expected a 640×400 SVG")
    elements = list(root.iter())
    if not 2 <= len(elements) <= 350:
        raise ValueError("SVG element limit exceeded")
    for element in elements:
        if element.tag not in {f"{{{_NS}}}{tag}" for tag in _TAGS}:
            raise ValueError("Unsupported SVG element")
        if element is not root and element.tag == f"{{{_NS}}}svg":
            raise ValueError("Nested SVG is unsupported")
        for key, value in element.attrib.items():
            if key not in _ATTRIBUTES:
                raise ValueError("Unsupported SVG attribute")
            if "url" in value.lower() and not re.fullmatch(r"url\(#[A-Za-z_][\w.-]*\)", value):
                raise ValueError("Only local SVG references are supported")
            if (
                key in {"fill", "stroke", "stop-color"}
                and value != "none"
                and not re.fullmatch(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?", value)
            ):
                if not re.fullmatch(r"url\(#[A-Za-z_][\w.-]*\)", value):
                    raise ValueError("SVG colors must be hex values or local gradient references")
    root.set("width", "640")
    root.set("height", "400")
    # Emit a conventional SVG root for browser and rasterizer compatibility.
    for element in elements:
        element.tag = element.tag.removeprefix(f"{{{_NS}}}")
    root.set("xmlns", _NS)
    payload = ET.tostring(root, encoding="utf-8")
    return "data:image/svg+xml;base64," + base64.b64encode(payload).decode("ascii")


class OpenRouterThumbnails:
    def __init__(self, client: httpx.Client, api_key: str, model: str, prompt: str) -> None:
        self._client, self._key, self._model, self._prompt = client, api_key, model, prompt

    def generate(
        self, title: str, description: str, topics: tuple[str, ...], *, visual_direction: str = ""
    ) -> str:
        if not self._key:
            raise ThumbnailUnavailable("Configure OpenRouter to generate thumbnails")
        try:
            response = self._client.post(
                "/api/v1/chat/completions",
                headers={"Authorization": "Bearer " + self._key},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": self._prompt},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "title": title,
                                    "description": description,
                                    "topics": topics,
                                    "visual_direction": visual_direction,
                                }
                            ),
                        },
                    ],
                    "reasoning": {"effort": "medium"},
                    "max_tokens": 12000,
                },
            )
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete SVG response")
            return svg_image_reference(choice["message"]["content"])
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            ET.ParseError,
        ) as exc:
            raise ThumbnailUnavailable(
                "Thumbnail generation failed. Your saved content is unchanged; try again."
            ) from exc
