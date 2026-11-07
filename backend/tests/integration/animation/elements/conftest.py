import httpx
import pytest
from fakes.animation_elements import ParallelElementProvider

from app.courses.adapters.ai.animation_elements import StoryboardElementAgent
from app.courses.adapters.ai.direct_animation import DirectAnimationCall


@pytest.fixture
def element_runtime(direct_canvas_runtime):
    author, author_provider, commands, inputs, root = direct_canvas_runtime
    provider = ParallelElementProvider()

    def clients():
        return httpx.Client(transport=httpx.MockTransport(provider))

    llm = DirectAnimationCall(clients, "test-key", "test-model", "low", max_output_tokens=16000)
    return (
        StoryboardElementAgent(root, commands.tools, llm),
        provider,
        author,
        author_provider,
        inputs,
        root,
    )
