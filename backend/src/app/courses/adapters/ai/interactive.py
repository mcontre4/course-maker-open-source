import asyncio
import json
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, replace
from html.parser import HTMLParser
from typing import Annotated

from httpx import HTTPError
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError

from app.courses.adapters.ai.agent_sessions import AgentSessionRun, PersistentAgentSessions
from app.courses.domain.errors import CourseError
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_interactive import InteractiveDetails, InteractivePage
from app.courses.ports.lesson_interactive import (
    InteractiveAgent,
    InteractiveAgentRequest,
    InteractiveGenerationUnavailable,
)


class _SelfContainedPage(HTMLParser):
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            (tag == "script" and "src" in attributes)
            or tag
            in {
                "form",
                "iframe",
                "object",
                "embed",
                "base",
                "link",
            }
            or (tag == "meta" and (attributes.get("http-equiv") or "").lower() == "refresh")
        ):
            raise CourseError(
                "The generated page needs external resources or navigation. Please retry."
            )
        for name, value in attrs:
            if name in {"src", "href", "xlink:href", "poster", "action", "srcset"} and value:
                if value.startswith("#") or (tag == "img" and value.startswith(("data:", "blob:"))):
                    continue
                raise CourseError(
                    "The generated page uses external assets. Please retry the build."
                )


class InteractiveDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    html: str
    title: Annotated[str, Field(max_length=80)] | None
    goal: Annotated[str, Field(max_length=200)] | None
    prompts: (
        Annotated[list[Annotated[str, Field(min_length=1, max_length=160)]], Field(max_length=6)]
        | None
    )

    def page(self, *, first: bool) -> InteractivePage:
        details = None
        if first:
            details = InteractiveDetails(
                self.title or "", self.goal or "", tuple(self.prompts or ())
            )
            if not details.goal or not 2 <= len(details.prompts) <= 4:
                raise CourseError("The first build needs a goal and 2 to 4 things to try.")
        page = InteractivePage(self.html, details)
        parser = _SelfContainedPage()
        parser.feed(page.html)
        parser.close()
        return page


def validate_interactive(
    ctx: RunContext[InteractiveAgentRequest],
    draft: InteractiveDraft,
) -> InteractiveDraft:
    try:
        draft.page(first=ctx.deps.current_html is None)
    except CourseError as exc:
        raise ModelRetry(str(exc)) from exc
    return draft


class PydanticInteractiveAgent:
    def __init__(
        self,
        scope: Callable[
            [], AbstractAsyncContextManager[Agent[InteractiveAgentRequest, InteractiveDraft]]
        ],
        sessions: PersistentAgentSessions | None = None,
    ) -> None:
        self._scope = scope
        self._sessions = sessions or PersistentAgentSessions()

    def run(self, request: InteractiveAgentRequest) -> InteractivePage:
        try:
            return asyncio.run(self._run(request))
        except (AgentRunError, APIError, HTTPError, TimeoutError) as exc:
            raise InteractiveGenerationUnavailable(
                "The interactive builder could not finish a valid, self-contained page "
                "within the 512 KiB limit. Please retry or simplify the request."
            ) from exc

    async def _run(self, request: InteractiveAgentRequest) -> InteractivePage:
        async def turn(state: AgentSessionRun) -> InteractivePage:
            async with self._scope() as agent:
                prompt = asdict(request)
                prompt.pop("session", None)
                result = await agent.run(
                    json.dumps(prompt),
                    conversation=state.conversation,
                    deps=request,
                    usage_limits=state.limits(request_limit=3, total_tokens_limit=60000),
                    timeout=300,
                )
                state.capture(result)
                return replace(
                    result.output.page(first=request.current_html is None),
                    session_id=state.session_id,
                )

        return (await self._sessions.run(request.session, "interactive", turn)).output


@dataclass(frozen=True)
class RoutedInteractiveAgent:
    agents: Mapping[GenerationMode, InteractiveAgent]

    def run(self, request: InteractiveAgentRequest) -> InteractivePage:
        return self.agents[request.generation_mode].run(request)
