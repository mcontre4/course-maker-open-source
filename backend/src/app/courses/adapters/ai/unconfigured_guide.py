from collections.abc import Callable

from app.courses.ports.guide import (
    GuideAgentRequest,
    GuideAgentResponse,
    GuideToolRequest,
    GuideToolResponse,
)
from app.courses.ports.lesson_agent import LessonGenerationUnavailable


class UnconfiguredGuideAgent:
    def run(
        self, request: GuideAgentRequest, tool: Callable[[GuideToolRequest], GuideToolResponse]
    ) -> GuideAgentResponse:
        raise LessonGenerationUnavailable("Configure OpenRouter to use your guide")
