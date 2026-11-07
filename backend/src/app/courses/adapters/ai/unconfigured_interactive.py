from app.courses.domain.lesson_interactive import InteractivePage
from app.courses.ports.lesson_interactive import (
    InteractiveAgentRequest,
    InteractiveGenerationUnavailable,
)


class UnconfiguredInteractiveAgent:
    def run(self, request: InteractiveAgentRequest) -> InteractivePage:
        raise InteractiveGenerationUnavailable(
            "Interactive generation is not configured. Configure OpenRouter and retry the build."
        )
