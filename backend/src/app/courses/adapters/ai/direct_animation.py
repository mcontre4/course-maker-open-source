"""Single-request author and pixel reviewer; execution remains in the offline worker."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from app.courses.adapters.ai.canvas_animator import CanvasAnimator
from app.courses.adapters.ai.model_options import model_options
from app.courses.adapters.ai.spend import ProviderUsageTracking
from app.courses.adapters.ai.visual_reference import (
    preferred_style_example,
    select_teaching_example,
    teaching_example_identity,
)
from app.courses.application.run_agent_session import AgentSessionFactory
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.animator import AnimationUnavailable

if TYPE_CHECKING:
    from pydantic_ai import Conversation

    from app.courses.adapters.ai.agent_sessions import (
        AgentSessionRun,
        PersistentAgentSessions,
        SessionResult,
    )

MAX_OUTPUT_TOKENS = 120000


def direct_messages(conversation: Conversation) -> list[dict[str, Any]]:
    """Map the direct worker's native text/image messages to its existing transport."""
    from pydantic_ai.messages import (
        ImageUrl,
        ModelRequest,
        SystemPromptPart,
        TextPart,
        UserPromptPart,
    )

    messages: list[dict[str, Any]] = []
    for message in conversation.messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    messages.append({"role": "system", "content": part.content})
                elif isinstance(part, UserPromptPart):
                    original_content = part.content
                    wire_content: str | list[dict[str, Any]]
                    if isinstance(original_content, str):
                        wire_content = original_content
                    else:
                        wire_content = [
                            {"type": "text", "text": item}
                            if isinstance(item, str)
                            else {
                                "type": "image_url",
                                "image_url": {"url": item.url, "detail": "high"},
                            }
                            for item in original_content
                            if isinstance(item, (str, ImageUrl))
                        ]
                    messages.append({"role": "user", "content": wire_content})
        else:
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(p.content for p in message.parts if isinstance(p, TextPart)),
                }
            )
    return messages


class DirectAnimationCall:
    def __init__(
        self,
        clients: Callable[[], AbstractContextManager[httpx.Client]],
        key: str,
        model: str,
        effort: str,
        tracking: ProviderUsageTracking | None = None,
        sessions: PersistentAgentSessions | None = None,
        *,
        session_factory: AgentSessionFactory | None = None,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        self._clients, self._key, self.model, self.effort = clients, key, model, effort
        self._tracking = tracking
        self._sessions, self._session_factory = sessions, session_factory
        self._max_output_tokens = max_output_tokens

    def complete(self, system: str, content: list[dict[str, Any]], stage: str) -> str:
        return self.complete_with_session(system, content, stage).output

    def complete_with_session(
        self,
        system: str,
        content: list[dict[str, Any]],
        stage: str,
        context: AgentSessionContext | None = None,
    ) -> SessionResult[str]:
        from pydantic_ai import Conversation, ConversationTypeAdapter
        from pydantic_ai.messages import (
            ImageUrl,
            ModelRequest,
            ModelResponse,
            SystemPromptPart,
            TextPart,
            UserPromptPart,
        )

        from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions

        async def turn(state: AgentSessionRun) -> str:
            conversation = state.conversation or Conversation()
            user = [
                part["text"] if part["type"] == "text" else ImageUrl(part["image_url"]["url"])
                for part in content
            ]
            conversation.messages.append(
                ModelRequest(
                    parts=[
                        SystemPromptPart(system),
                        UserPromptPart(user),
                    ]
                )
            )
            result = self._request(direct_messages(conversation), stage)
            conversation.messages.append(
                ModelResponse(
                    parts=[TextPart(result)],
                    model_name=self.model,
                    provider_name="openrouter",
                    conversation_id=conversation.conversation_id,
                )
            )
            conversation.usage.requests += 1
            state.history_json = ConversationTypeAdapter.dump_json(conversation).decode()
            return result

        return asyncio.run(
            (self._sessions or PersistentAgentSessions(self._session_factory)).run(
                context,
                {
                    "visual_review": "reviewer",
                    "element_planning": "visual_elements",
                    "element_generation": "visual_elements",
                }.get(stage, "animator"),
                turn,
            )
        )

    def _request(self, messages: list[dict[str, Any]], stage: str) -> str:
        if not self._key:
            raise AnimationUnavailable("Configure OpenRouter for direct animation generation")
        try:
            with (
                self._tracking.worker(stage, backend="direct") if self._tracking else nullcontext(),
                self._clients() as client,
            ):
                response = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": "Bearer " + self._key},
                    json={
                        **model_options(self.model),
                        "messages": messages,
                        "reasoning": {"effort": self.effort},
                        "max_tokens": self._max_output_tokens,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                error = data.get("error")
                if isinstance(error, dict):
                    raise AnimationUnavailable(
                        f"Direct LLM {stage} provider error ({error.get('code', 'unknown')}): "
                        + str(error.get("message", "No error details supplied"))[:500]
                    )
                choice = data["choices"][0]
                result = choice["message"]["content"]
                if choice.get("finish_reason") == "length":
                    raise AnimationUnavailable(
                        f"Direct LLM {stage} generation reached its "
                        f"{self._max_output_tokens}-token output limit "
                        "(including reasoning) before completing. Retry with lower reasoning "
                        "effort or a different model."
                    )
                if choice.get("finish_reason") != "stop" or not isinstance(result, str):
                    raise ValueError("Incomplete model response")
                if not result.strip() or len(result.encode()) > 600000:
                    raise ValueError("Missing or oversized model output")
                return result.strip()
        except httpx.HTTPStatusError as exc:
            raise AnimationUnavailable(
                f"Direct LLM {stage} request failed (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AnimationUnavailable(f"Direct LLM {stage} request timed out") from exc
        except httpx.HTTPError as exc:
            raise AnimationUnavailable(
                f"Direct LLM {stage} connection failed ({type(exc).__name__}). "
                "Completed stages are saved; retry generation."
            ) from exc
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
        ) as exc:
            logging.getLogger(__name__).exception("Invalid direct LLM %s response", stage)
            raise AnimationUnavailable(
                "Direct LLM request failed or returned incomplete output"
            ) from exc


def unfence(text: str) -> str:
    if text.startswith("```") and text.endswith("```") and "\n" in text:
        return text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


class DirectCanvasAnimator(CanvasAnimator):
    def __init__(self, *args: Any, llm: DirectAnimationCall, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._llm = llm

    def _authoring_identity(self, prompt_file: str) -> list[str]:
        return [
            "direct-v1",
            self._llm.model,
            self._llm.effort,
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            hashlib.sha256(
                Path(__file__).with_name("visual_reference.py").read_bytes()
            ).hexdigest(),
            Path(__file__).with_name(prompt_file).read_text(),
            teaching_example_identity(self._tools),
        ]

    def _author(self, job: Path, prompt_file: str, prompt: str, name: str) -> None:
        system = (
            Path(__file__).with_name(prompt_file).read_text()
            + (
                "\nAll needed files are supplied below. You have no tools. "
                "Return ONLY the complete "
                "animation.js source, without Markdown or commentary. The platform saves the file "
                "and runs validation. Do not return patches or implementation notes. "
                "Keep the source compact. "
                "Reuse drawing helpers and data-driven scene functions instead of duplicating "
                "code. Complete every scene. "
            )
            + (
                "Review suggestions are optional presentation fixes. For anything that requires "
                "new input or cannot be fixed locally, preserve the existing source for that part. "
                "Return complete JavaScript even when some suggestions cannot be addressed."
                if name.startswith("repair")
                else "Adapt unavailable visuals yourself using the supplied resources. "
                "Return complete JavaScript even when the storyboard cannot be followed exactly. "
                "Never request changes, assets, datasets or approval."
            )
        )
        files = [job / "inputs.json", job / "javascript/timeline.json"]
        style = job / "javascript/style"
        files += [style / f for f in ("STYLE.md", "drawing.js", "harness.js", "sound.js")]
        example = preferred_style_example(style)
        if example is not None:
            files.append(example)
        if (job / "javascript/animation.js").is_file():
            files.append(job / "javascript/animation.js")
        inputs = json.loads((job / "inputs.json").read_text())
        teaching = select_teaching_example(
            self._tools, inputs["visual_style_id"], inputs["storyboard"]
        )
        supplied = {str(path.relative_to(job)): path.read_text() for path in files}
        if teaching is not None:
            reference_style = json.loads(teaching.notes)["origin"]["style_id"]
            if reference_style == inputs["visual_style_id"]:
                if example is not None:
                    supplied.pop(str(example.relative_to(job)))
            supplied["teaching-reference/sequence.json"] = teaching.notes
            # Cross-medium history examples use incompatible drawing helpers.
            # Their notes/pixels still teach structure; retain the selected medium's code.
            if reference_style in (None, inputs["visual_style_id"]):
                supplied["teaching-reference/animation.js"] = teaching.source.read_text()
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": prompt
                + "\n"
                + json.dumps(
                    supplied,
                    ensure_ascii=False,
                ),
            }
        ]
        reference_images = [style / "reference.png"]
        if teaching is not None:
            reference_images.append(teaching.image)
        for reference_image in reference_images:
            if not reference_image.is_file():
                continue
            content.extend(
                [
                    {
                        "type": "text",
                        "text": "Reference pixels: "
                        + (
                            "javascript/style/reference.png"
                            if reference_image.parent == style
                            else "teaching-reference/" + reference_image.name
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(reference_image.read_bytes()).decode(),
                            "detail": "high",
                        },
                    },
                ]
            )
        inputs = json.loads((job / "inputs.json").read_text())
        scope = AgentSessionContext(**inputs["session"]) if inputs.get("session") else None
        if scope and name == "author-best-effort" and (job / "agent-session-id").is_file():
            from dataclasses import replace

            scope = replace(scope, session_id=(job / "agent-session-id").read_text())
        completed = self._llm.complete_with_session(
            system,
            content,
            "animation_repair" if name.startswith("repair") else "animation",
            scope,
        )
        if completed.session_id:
            (job / "agent-session-id").write_text(completed.session_id)
        source = unfence(completed.output)
        if source.startswith("{"):
            try:
                change = json.loads(source)
            except ValueError:
                change = None
            if isinstance(change, dict) and "requested_change" in change:
                (job / "change-request.json").write_text(source)
                return
        (job / "javascript/animation.js").write_text(source)


class DirectCanvasReviewer:
    def __init__(self, llm: DirectAnimationCall) -> None:
        self._llm = llm

    def arguments(self) -> list[str]:
        return [
            "direct-review-v1",
            self._llm.model,
            self._llm.effort,
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            Path(__file__).with_name("canvas_review_prompt.md").read_text(),
            "-",
        ]

    def run_job(self, job: Path, kind: str, args: list[str], prompt: str | None, name: str) -> None:
        system = Path(__file__).with_name("canvas_review_prompt.md").read_text() + (
            "\nYou have no tools. All evidence is attached. Return ONLY the review JSON object; "
            "the platform writes review.json. Review the provided stills honestly."
        )
        evidence = [job / "javascript/style/reference.png"]
        evidence += sorted((job / "render").glob("contact-*.png"))
        evidence += sorted((job / "render").glob("motion-*.png"))
        # Closing frames reveal small overlaps that contact-sheet thumbnails can hide.
        timeline = json.loads((job / "javascript/timeline.json").read_text())
        for scene in timeline["scenes"]:
            closing = min(
                timeline["duration_frames"] - 1,
                scene["start_frame"] + scene["duration_frames"] - 1,
            )
            still = job / "render" / f"frame-{closing:06d}.png"
            if not still.is_file():
                raise AnimationUnavailable("Missing rendered scene-closing evidence")
            evidence.append(still)
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "instructions": prompt,
                        "inputs": json.loads((job / "inputs.json").read_text()),
                        "timeline": timeline,
                        "visual_plan": json.loads((job / "render/visual-plan.json").read_text()),
                    },
                    ensure_ascii=False,
                ),
            }
        ]
        for path in dict.fromkeys(evidence):
            if not path.is_file():
                raise AnimationUnavailable("Missing rendered review evidence")
            content += [
                {"type": "text", "text": str(path.relative_to(job))},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(path.read_bytes()).decode(),
                        "detail": "high",
                    },
                },
            ]
        inputs = json.loads((job / "inputs.json").read_text())
        scope = AgentSessionContext(**inputs["session"]) if inputs.get("session") else None
        if scope:
            from dataclasses import replace

            scope = replace(scope, session_id=inputs.get("reviewer_session_id"))
        result = self._llm.complete_with_session(system, content, "visual_review", scope)
        report = json.loads(unfence(result.output))
        if isinstance(report, dict) and result.session_id:
            report["session_id"] = result.session_id
        (job / "review.json").write_text(json.dumps(report))
