from app.courses.ports.storyboard_agent import (
    StoryboardAgentRequest,
    StoryboardAgentResponse,
    StoryboardGenerationUnavailable,
)


class UnconfiguredStoryboardAgent:
    def run(self, request: StoryboardAgentRequest) -> StoryboardAgentResponse:
        raise StoryboardGenerationUnavailable("Configure OpenRouter to generate storyboards")
