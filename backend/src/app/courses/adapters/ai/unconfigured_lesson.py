from app.courses.ports.lesson_agent import (
    LessonAgentRequest,
    LessonAgentResponse,
    LessonGenerationUnavailable,
)


class UnconfiguredLessonAgent:
    def run(self, request: LessonAgentRequest) -> LessonAgentResponse:
        raise LessonGenerationUnavailable(
            "Lesson generation needs OpenRouter and Tavily credentials"
        )
