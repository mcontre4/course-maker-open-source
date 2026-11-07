from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from fakes.lesson_interactive import HTML, interactive_page
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.courses.adapters.ai.interactive import (
    InteractiveDraft,
    PydanticInteractiveAgent,
    RoutedInteractiveAgent,
    validate_interactive,
)
from app.courses.adapters.ai.unconfigured_interactive import UnconfiguredInteractiveAgent
from app.courses.composition import build_interactive_agent
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_interactive import MAX_HTML_BYTES
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.lesson_interactive import (
    InteractiveAgentRequest,
    InteractiveGenerationUnavailable,
)
from app.shared.infrastructure.settings import Settings

pytestmark = pytest.mark.integration


def request():
    return InteractiveAgentRequest(
        "Gravity",
        "A lesson",
        ("Gravity",),
        "Beginners",
        None,
        "A lab",
        "A lab",
        None,
        GenerationMode.FAST,
    )


@pytest.mark.parametrize("invalid", [None, "external", "incomplete", "oversize", "provider"])
def test_real_agent_validates_pages_retries_and_closes_scope(invalid):
    calls, closed = [], []

    def model(messages, info):
        calls.append(messages)
        if invalid == "provider":
            raise TimeoutError("provider secret")
        html = HTML
        if len(calls) == 1:
            if invalid == "external":
                html = HTML.replace(
                    "</head>", '<script src="https://example.com/a.js"></script></head>'
                )
            elif invalid == "incomplete":
                html = "<p>Only a fragment</p>"
            elif invalid == "oversize":
                html = HTML + "x" * MAX_HTML_BYTES
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {
                        "html": html,
                        "title": "Gravity lab",
                        "goal": "Explore gravity.",
                        "prompts": ["Change gravity.", "Reset the experiment."],
                    },
                )
            ]
        )

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model),
            output_type=InteractiveDraft,
            deps_type=InteractiveAgentRequest,
            retries=1,
        )
        agent.output_validator(validate_interactive)
        try:
            yield agent
        finally:
            closed.append(True)

    runner = PydanticInteractiveAgent(scope)
    if invalid == "provider":
        with pytest.raises(InteractiveGenerationUnavailable, match="could not finish"):
            runner.run(request())
    else:
        assert runner.run(request()) == interactive_page()
        assert len(calls) == (1 if invalid is None else 2)
    assert closed == [True]


@pytest.mark.parametrize(
    "element",
    [
        "<form><input></form>",
        '<iframe srcdoc="hi"></iframe>',
        '<meta http-equiv="refresh" content="0;url=https://example.com">',
        '<link rel="stylesheet" href="https://example.com/style.css">',
        '<img src="https://example.com/image.png">',
        '<script src="#inline"></script>',
        '<script src=""></script>',
        '<svg><image xlink:href="https://example.com/image.svg"/></svg>',
    ],
)
def test_repeated_invalid_output_fails_with_plain_retryable_message(element):
    @asynccontextmanager
    async def scope():
        def model(messages, info):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        info.output_tools[0].name,
                        {
                            "html": HTML.replace("</body>", element + "</body>"),
                            "title": "Lab",
                            "goal": "Explore",
                            "prompts": ["Try", "Reset"],
                        },
                    )
                ]
            )

        agent = Agent(
            FunctionModel(model),
            output_type=InteractiveDraft,
            deps_type=InteractiveAgentRequest,
            retries=1,
        )
        agent.output_validator(validate_interactive)
        yield agent

    with pytest.raises(InteractiveGenerationUnavailable):
        PydanticInteractiveAgent(scope).run(request())


def test_changes_do_not_require_generated_metadata_and_mode_routing():
    draft = InteractiveDraft(html=HTML, title=None, goal=None, prompts=None)
    assert draft.page(first=False).details is None
    page = interactive_page()

    class Agent:
        def run(self, req):
            return page

    routed = RoutedInteractiveAgent({GenerationMode.FAST: Agent()})
    assert routed.run(replace(request(), current_html=HTML)) == page


def test_composition_honors_override_and_unconfigured_provider():
    config = Settings(
        _env_file=None,
        database_url="mysql+pymysql://test:test@localhost/test",
        api_key="interactive-test-secret-0123456789",
        openrouter_api_key="",
    )
    assert isinstance(build_interactive_agent(config), UnconfiguredInteractiveAgent)
    with pytest.raises(InteractiveGenerationUnavailable, match="not configured"):
        build_interactive_agent(config).run(request())
    configured = config.model_copy(update={"openrouter_api_key": type(config.api_key)("fake")})
    routed = build_interactive_agent(configured, model_override=AnimatorModel.TERRA_FAST)
    assert set(routed.agents) == set(GenerationMode)
