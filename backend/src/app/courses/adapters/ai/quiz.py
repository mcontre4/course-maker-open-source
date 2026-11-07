import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from typing import Annotated, Literal

from httpx import HTTPError
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError

from app.courses.adapters.ai.agent_sessions import AgentSessionRun, PersistentAgentSessions
from app.courses.domain.errors import CourseError
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_quiz import LessonQuiz, LessonQuizQuestion
from app.courses.ports.lesson_quiz import (
    QuizAgentRequest,
    QuizAgentResponse,
    QuizGenerationUnavailable,
)


class QuestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["multiple_choice"]
    prompt: Annotated[str, Field(min_length=1, max_length=500)]
    options: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=300)]], Field(min_length=2, max_length=6)
    ]
    correct_index: Annotated[int, Field(ge=0, strict=True)]
    explanation: Annotated[str, Field(min_length=1, max_length=800)]


class QuizDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: Annotated[list[QuestionDraft], Field(min_length=1, max_length=20)]

    def domain_questions(self) -> tuple[LessonQuizQuestion, ...]:
        return tuple(
            LessonQuizQuestion(
                f"question_{i}", q.kind, q.prompt, tuple(q.options), q.correct_index, q.explanation
            )
            for i, q in enumerate(self.questions, 1)
        )


def validate_quiz(ctx: RunContext[QuizAgentRequest], draft: QuizDraft) -> QuizDraft:
    try:
        LessonQuiz(LessonId(ctx.deps.plan.lesson_id), draft.domain_questions(), "generated")
    except CourseError as exc:
        raise ModelRetry(str(exc)) from exc
    return draft


class PydanticQuizAgent:
    def __init__(
        self,
        scope: Callable[[], AbstractAsyncContextManager[Agent[QuizAgentRequest, QuizDraft]]],
        sessions: PersistentAgentSessions | None = None,
    ) -> None:
        self._scope = scope
        self._sessions = sessions or PersistentAgentSessions()

    def run(self, request: QuizAgentRequest) -> QuizAgentResponse:
        try:
            return asyncio.run(self._run(request))
        except (AgentRunError, APIError, HTTPError, TimeoutError) as exc:
            raise QuizGenerationUnavailable(
                "Quiz generation failed; your saved quiz is unchanged. Please try again"
            ) from exc

    async def _run(self, request: QuizAgentRequest) -> QuizAgentResponse:
        async def turn(state: AgentSessionRun) -> QuizAgentResponse:
            async with self._scope() as agent:
                prompt = asdict(request)
                prompt.pop("session", None)
                result = await agent.run(
                    json.dumps(prompt),
                    conversation=state.conversation,
                    deps=request,
                    usage_limits=state.limits(request_limit=3, total_tokens_limit=20000),
                    timeout=180,
                )
                state.capture(result)
                return QuizAgentResponse(result.output.domain_questions(), state.session_id)

        return (await self._sessions.run(request.session, "quiz", turn)).output
