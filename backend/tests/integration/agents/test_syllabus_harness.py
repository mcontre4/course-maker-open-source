import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from fakes.tavily import RecordingTavilyClient
from fixtures.syllabus import course_context, curriculum
from pydantic_ai import Agent, ConversationTypeAdapter
from pydantic_ai.common_tools.tavily import tavily_search_tool
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel

from app.courses.adapters.ai.syllabus import (
    AgentOutput,
    PydanticSyllabusAgent,
    ScopedSyllabusAgent,
    current_course,
    prepare_search,
    validate_curriculum,
)
from app.courses.domain.duration import Duration
from app.courses.ports.syllabus_agent import SyllabusAgentRequest
from app.courses.ports.syllabus_errors import SyllabusUnavailable

pytestmark = pytest.mark.integration


def final_output(info, plan=None, message="Updated syllabus"):
    return ModelResponse(
        parts=[
            ToolCallPart(
                info.output_tools[0].name,
                {
                    "message": message,
                    "curriculum": asdict(plan) if plan is not None else None,
                },
            )
        ]
    )


class ResearchModel:
    def __init__(self):
        self.requests = []

    def __call__(self, messages, info):
        self.requests.append((list(messages), info.instructions))
        if isinstance(messages[-1], ModelRequest) and isinstance(
            messages[-1].parts[-1], ToolReturnPart
        ):
            return final_output(info, curriculum(), "See https://docs.python.org/3/tutorial/")
        return ModelResponse(
            parts=[ToolCallPart("tavily_search", {"query": "Python official tutorial"})]
        )


def test_real_agent_searches_and_restores_durable_conversation():
    client, model = RecordingTavilyClient(), ResearchModel()
    agent = Agent(
        FunctionModel(model),
        deps_type=str,
        output_type=AgentOutput,
        system_prompt=Path("src/app/courses/adapters/ai/syllabus_prompt.md").read_text(),
        instructions=[current_course],
        tools=[tavily_search_tool(client=client, max_results=5, search_depth="basic")],
    )
    first = PydanticSyllabusAgent(agent).run(
        SyllabusAgentRequest("  Teach Python  ", "[]", course_context("saved version 1"))
    )
    assert first.curriculum.title == "Python"
    assert client.queries[0][0] == "Python official tutorial"
    assert client.queries[0][1]["max_results"] == 5
    assert client.queries[0][1]["search_depth"] == "basic"
    assert "saved version 1" in model.requests[0][1]
    restored = ConversationTypeAdapter.validate_json(first.history_json)
    assert any(isinstance(part, ToolReturnPart) for msg in restored.messages for part in msg.parts)
    assert [
        part.content
        for msg in restored.messages
        for part in msg.parts
        if isinstance(part, UserPromptPart)
    ] == ["  Teach Python  "]
    second_agent = Agent(
        FunctionModel(model),
        deps_type=str,
        output_type=AgentOutput,
        instructions=[current_course],
        tools=[tavily_search_tool(client=client, max_results=5)],
    )
    second = PydanticSyllabusAgent(second_agent).run(
        SyllabusAgentRequest("Add a project", first.history_json, course_context("saved version 2"))
    )
    messages = ConversationTypeAdapter.validate_json(second.history_json).messages
    assert [
        part.content for msg in messages for part in msg.parts if isinstance(part, UserPromptPart)
    ] == ["  Teach Python  ", "Add a project"]
    assert "saved version 2" in model.requests[-1][1]
    history = second.history_json
    for _ in range(7):
        turn = PydanticSyllabusAgent(second_agent).run(
            SyllabusAgentRequest("Another refinement", history, course_context())
        )
        history = turn.history_json
    assert len(client.queries) == 9
    assert (
        ConversationTypeAdapter.validate_json(history).conversation_id == restored.conversation_id
    )


def test_model_timeout_is_mapped_to_application_error():
    def unavailable(messages, info):
        raise TimeoutError("Provider internals must not appear in HTTP responses")

    adapter = PydanticSyllabusAgent(
        Agent(FunctionModel(unavailable), output_type=AgentOutput, deps_type=str)
    )
    with pytest.raises(SyllabusUnavailable, match="Syllabus generation failed"):
        adapter.run(SyllabusAgentRequest("Teach Python", "[]", course_context()))


def test_invalid_model_curriculum_is_retried_before_returning():
    calls = []

    def invalid_then_valid(messages, info):
        calls.append(messages)
        plan = asdict(curriculum())
        if len(calls) == 1:
            plan["chapters"][0]["lessons"][0]["video_minutes"] = -1
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"message": "Done", "curriculum": plan})]
        )

    adapter = PydanticSyllabusAgent(
        Agent(FunctionModel(invalid_then_valid), deps_type=str, output_type=AgentOutput, retries=2)
    )
    result = adapter.run(SyllabusAgentRequest("Teach Python", "[]", course_context()))
    assert result.curriculum.chapters[0].lessons[0].video_minutes == 10
    assert len(calls) == 2


@pytest.mark.parametrize("incomplete", [False, True])
def test_invalid_schedule_is_corrected_before_returning(incomplete):
    calls = []

    def invalid_then_valid(messages, info):
        calls.append(messages)
        plan = asdict(curriculum())
        if incomplete:
            if len(calls) > 1:
                plan["chapters"][0]["lessons"][1]["week"] = 2
        elif len(calls) == 1:
            plan["chapters"][0]["lessons"][0]["practice_minutes"] = 1000
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"message": "Done", "curriculum": plan})]
        )

    agent = Agent(
        FunctionModel(invalid_then_valid), deps_type=str, output_type=AgentOutput, retries=2
    )
    agent.output_validator(validate_curriculum)
    duration = (
        Duration("weekly", weeks=2, hours_per_week=2) if incomplete else Duration("total", hours=2)
    )
    result = PydanticSyllabusAgent(agent).run(
        SyllabusAgentRequest("Teach Python", "[]", course_context(duration=duration))
    )
    result.curriculum.validate_budget(duration)
    assert len(calls) == 2


def test_agent_can_finish_when_its_tavily_search_budget_is_exhausted():
    client = RecordingTavilyClient()

    def search_until_budget(messages, info):
        if any(tool.name == "tavily_search" for tool in info.function_tools):
            return ModelResponse(parts=[ToolCallPart("tavily_search", {"query": "official docs"})])
        return final_output(info, curriculum())

    agent = Agent(
        FunctionModel(search_until_budget),
        deps_type=str,
        output_type=AgentOutput,
        tools=[replace(tavily_search_tool(client=client, max_results=5), prepare=prepare_search)],
    )
    result = PydanticSyllabusAgent(agent).run(
        SyllabusAgentRequest("Research Python", "[]", course_context())
    )
    assert result.curriculum is not None and len(client.queries) == 6


def test_provider_scope_is_closed_on_its_own_loop_for_concurrent_requests():
    opened, closed = [], []

    @asynccontextmanager
    async def scope():
        loop = asyncio.get_running_loop()
        opened.append(loop)
        try:
            yield Agent(
                FunctionModel(lambda messages, info: final_output(info)),
                deps_type=str,
                output_type=AgentOutput,
            )
        finally:
            assert asyncio.get_running_loop() is loop
            closed.append(loop)

    adapter = ScopedSyllabusAgent(scope)
    requests = [SyllabusAgentRequest(f"Request {i}", "[]", course_context()) for i in range(4)]
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(adapter.run, requests))
    assert len(results) == 4
    assert len(set(opened)) == 4 and set(opened) == set(closed)


def test_openrouter_responses_request_and_structured_output_without_network():
    from httpx2 import AsyncClient, MockTransport, Response
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    requests = []

    def respond(request):
        requests.append(request)
        return Response(
            200,
            json={
                "id": "resp_offline",
                "object": "response",
                "created_at": 1,
                "model": "openai/gpt-6.1-sol",
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "id": "fc_offline",
                        "call_id": "call_offline",
                        "name": "final_result",
                        "arguments": json.dumps(
                            {
                                "message": "What subject would you like to learn?",
                                "curriculum": None,
                            }
                        ),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            },
        )

    @asynccontextmanager
    async def scope():
        async with AsyncClient(transport=MockTransport(respond)) as http:
            async with AsyncOpenAI(
                api_key="offline-test-key",
                base_url="https://openrouter.ai/api/v1",
                http_client=http,
            ) as client:
                model = OpenAIResponsesModel(
                    "openai/gpt-6.1-sol", provider=OpenRouterProvider(openai_client=client)
                )
                yield Agent(
                    model,
                    deps_type=str,
                    output_type=AgentOutput,
                    model_settings=OpenAIResponsesModelSettings(openai_store=False),
                    tools=[tavily_search_tool(client=RecordingTavilyClient(), max_results=5)],
                )

    result = ScopedSyllabusAgent(scope).run(
        SyllabusAgentRequest("Help me learn", "[]", course_context())
    )
    assert result.curriculum is None
    assert str(requests[0].url) == "https://openrouter.ai/api/v1/responses"
    body = json.loads(requests[0].content)
    assert body["model"] == "openai/gpt-6.1-sol" and body["store"] is False
    assert any(tool["name"] == "tavily_search" for tool in body["tools"])
