from app.courses.ports.lesson_quiz import (
    QuizAgentRequest,
    QuizAgentResponse,
    QuizGenerationUnavailable,
)


class UnconfiguredQuizAgent:
    def run(self, request: QuizAgentRequest) -> QuizAgentResponse:
        raise QuizGenerationUnavailable("Configure OpenRouter to generate lesson quizzes")
