from contextlib import asynccontextmanager
from dataclasses import asdict, replace

import pytest
from fakes.tavily import RecordingTavilyClient
from fixtures.lesson_plan import lesson_plan
from fixtures.syllabus import make_planned_course
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from app.courses.adapters.ai.lesson import PydanticLessonAgent, validate_plan
from app.courses.domain.lesson_plan import LessonPlan, ResearchSource
from app.courses.ports.lesson_agent import LessonAgentRequest, LessonGenerationUnavailable

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("at_limits", [False, True])
def test_real_agent_executes_search_and_validates_lesson_output(at_limits):
    _, curriculum = make_planned_course()
    chapter = curriculum.chapters[0]
    brief = chapter.lessons[0]
    request = LessonAgentRequest("Python", brief, curriculum.guide, chapter, None, None)
    search = RecordingTavilyClient()
    closed = []
    plan = lesson_plan(brief)
    if at_limits:
        # A plan at each structural boundary must still be accepted without retries.
        seconds, remainder = divmod(brief.video_minutes * 60, 6)
        plan = replace(
            plan,
            beats=tuple(
                replace(
                    plan.beats[0],
                    teaching_notes="word " * 50,
                    seconds=seconds + (remainder if i == 0 else 0),
                    check_question=plan.beats[0].check_question if i == 0 else "",
                    expected_answer=plan.beats[0].expected_answer if i == 0 else "",
                )
                for i in range(6)
            ),
            examples=(replace(plan.examples[0], steps=("Step",) * 3),),
        )

    def model(messages, info):
        if isinstance(messages[-1], ModelRequest) and isinstance(
            messages[-1].parts[-1], ToolReturnPart
        ):
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, asdict(plan))])
        return ModelResponse(
            parts=[ToolCallPart("tavily_search", {"query": "Python official tutorial"})]
        )

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model),
            output_type=LessonPlan,
            deps_type=LessonAgentRequest,
            tools=[tavily_search_tool(client=search, max_results=5)],
        )
        agent.output_validator(validate_plan)
        try:
            yield agent
        finally:
            closed.append(True)

    result = PydanticLessonAgent(scope, "test-model").run(request)
    assert result.plan.lesson_id == brief.lesson_id
    assert result.plan == plan
    assert result.tool_calls == 1
    assert result.requests == 2
    assert search.queries[0][0] == "Python official tutorial"
    assert closed == [True]


@pytest.mark.parametrize(
    "invalid",
    [
        "unsearched_source",
        "fabricated_source",
        "bad_timing",
        "long_notes",
        "long_outline",
        "many_beats",
        "many_examples",
        "many_steps",
        "missing_check",
        "many_checks",
        "missing_feasibility",
        "off_by_one_second",
    ],
)
def test_agent_rejects_invalid_plans_or_unverified_citations(invalid):
    _, curriculum = make_planned_course()
    chapter = curriculum.chapters[0]
    brief = chapter.lessons[0]
    request = LessonAgentRequest("Python", brief, curriculum.guide, chapter, None, None)
    search = RecordingTavilyClient()

    def model(messages, info):
        if invalid != "unsearched_source" and not any(
            isinstance(part, ToolReturnPart) for message in messages for part in message.parts
        ):
            return ModelResponse(parts=[ToolCallPart("tavily_search", {"query": "Python"})])
        plan = lesson_plan(brief)
        if invalid == "fabricated_source":
            plan = replace(
                plan, sources=(ResearchSource("Invented", "https://example.com/absent"),)
            )
        if invalid == "bad_timing":
            plan = replace(plan, beats=(replace(plan.beats[0], seconds=1),))
        if invalid == "long_notes":
            plan = replace(plan, beats=(replace(plan.beats[0], teaching_notes="word " * 51),))
        if invalid == "long_outline":
            plan = replace(plan, required_facts=("word " * 601,))
        if invalid == "many_beats":
            seconds, remainder = divmod(brief.video_minutes * 60, 7)
            plan = replace(
                plan,
                beats=tuple(
                    replace(plan.beats[0], seconds=seconds + (remainder if i == 0 else 0))
                    for i in range(7)
                ),
            )
        if invalid == "many_examples":
            plan = replace(plan, examples=plan.examples * 2)
        if invalid == "many_steps":
            plan = replace(plan, examples=(replace(plan.examples[0], steps=("Step",) * 4),))
        if invalid == "missing_check":
            plan = replace(
                plan, beats=(replace(plan.beats[0], check_question="", expected_answer=""),)
            )
        if invalid == "many_checks":
            plan = replace(
                plan, beats=(replace(plan.beats[0], seconds=brief.video_minutes * 30),) * 2
            )
        if invalid == "missing_feasibility":
            plan = replace(plan, feasibility_status=None)
        if invalid == "off_by_one_second":
            plan = replace(
                plan, beats=(replace(plan.beats[0], seconds=brief.video_minutes * 60 - 1),)
            )
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, asdict(plan))])

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model),
            output_type=LessonPlan,
            deps_type=LessonAgentRequest,
            tools=[tavily_search_tool(client=search, max_results=5)],
            retries=1,
        )
        agent.output_validator(validate_plan)
        yield agent

    with pytest.raises(LessonGenerationUnavailable):
        PydanticLessonAgent(scope, "test-model").run(request)


def test_agent_can_shorten_an_outline_after_validator_feedback():
    _, curriculum = make_planned_course()
    chapter = curriculum.chapters[0]
    brief = chapter.lessons[0]
    request = LessonAgentRequest("Python", brief, curriculum.guide, chapter, None, None)
    search = RecordingTavilyClient()
    outputs = []

    def model(messages, info):
        if not any(isinstance(part, ToolReturnPart) for m in messages for part in m.parts):
            return ModelResponse(parts=[ToolCallPart("tavily_search", {"query": "Python"})])
        plan = lesson_plan(brief)
        if not outputs:
            seconds, remainder = divmod(brief.video_minutes * 60, 7)
            plan = replace(
                plan,
                required_facts=("word " * 601,),
                beats=tuple(
                    replace(
                        plan.beats[0],
                        teaching_notes="word " * 51,
                        seconds=seconds + (remainder if i == 0 else 0),
                    )
                    for i in range(7)
                ),
            )
        else:
            feedback = " ".join(
                str(part.content)
                for message in messages
                for part in message.parts
                if isinstance(part, ToolReturnPart) and part.outcome == "retried"
            )
            assert "six teaching beats" in feedback
            assert "50 words per beat" in feedback
            assert "600 words" in feedback
        outputs.append(plan)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, asdict(plan))])

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model),
            output_type=LessonPlan,
            deps_type=LessonAgentRequest,
            tools=[tavily_search_tool(client=search, max_results=5)],
            retries=1,
        )
        agent.output_validator(validate_plan)
        yield agent

    result = PydanticLessonAgent(scope, "test-model").run(request)
    assert result.plan == lesson_plan(brief)
    assert len(outputs) == 2
    assert result.requests == 3
    assert result.tool_calls == 1


@pytest.mark.parametrize("infeasible", [False, True])
def test_agent_accepts_unresearched_material_and_can_report_infeasibility(infeasible):
    from fixtures.lesson_plan import infeasible_lesson_plan

    _, curriculum = make_planned_course()
    chapter = curriculum.chapters[0]
    brief = chapter.lessons[0]
    request = LessonAgentRequest("Python", brief, curriculum.guide, chapter, None, None)
    plan = infeasible_lesson_plan(brief) if infeasible else replace(lesson_plan(brief), sources=())
    if infeasible:
        request = replace(request, description="A standalone lesson with excessive required scope")
    # Qualitative cases need not contain calculation-style solution steps.
    plan = replace(plan, examples=(replace(plan.examples[0], steps=()),))

    def model(messages, info):
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, asdict(plan))])

    @asynccontextmanager
    async def scope():
        agent = Agent(FunctionModel(model), output_type=LessonPlan, deps_type=LessonAgentRequest)
        agent.output_validator(validate_plan)
        yield agent

    result = PydanticLessonAgent(scope, "test-model").run(request)
    assert result.plan == plan
    assert result.requests == 1
    assert result.tool_calls == 0


def test_agent_accepts_one_diagnostic_across_multiple_beats():
    _, curriculum = make_planned_course()
    chapter = curriculum.chapters[0]
    brief = chapter.lessons[0]
    request = LessonAgentRequest("Python", brief, curriculum.guide, chapter, None, None)
    plan = lesson_plan(brief)
    plan = replace(
        plan, sources=(),
        beats=(
            replace(plan.beats[0], seconds=brief.video_minutes * 30),
            replace(plan.beats[0], seconds=brief.video_minutes * 30,
                    check_question="", expected_answer=""),
        ),
    )

    def model(messages, info):
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, asdict(plan))])

    @asynccontextmanager
    async def scope():
        agent = Agent(FunctionModel(model), output_type=LessonPlan, deps_type=LessonAgentRequest)
        agent.output_validator(validate_plan)
        yield agent

    assert PydanticLessonAgent(scope, "test-model").run(request).plan == plan


@pytest.mark.parametrize(
    ("estimated_seconds", "recommended_minutes", "accepted"),
    [
        (601, 11, True),
        (659, 11, True),
        (660, 11, True),
        (661, 12, True),
        (661, 11, False),
        (661, 13, False),
        (661, None, False),
        (661, 0, False),
        (661, -1, False),
        (661, 12.5, False),
    ],
)
def test_generated_duration_recommendations_round_up_all_beat_estimates(
    estimated_seconds, recommended_minutes, accepted
):
    from fixtures.lesson_plan import infeasible_lesson_plan

    _, curriculum = make_planned_course()
    chapter = curriculum.chapters[0]
    brief = chapter.lessons[0]
    request = LessonAgentRequest("Python", brief, curriculum.guide, chapter, None, None)
    plan = infeasible_lesson_plan(brief)
    first_seconds = estimated_seconds // 2
    plan = replace(
        plan,
        recommended_video_minutes=(estimated_seconds + 59) // 60,
        beats=(
            replace(plan.beats[0], seconds=first_seconds),
            replace(
                plan.beats[0], seconds=estimated_seconds - first_seconds,
                check_question="", expected_answer="",
            ),
        ),
    )

    output = asdict(plan)
    output["recommended_video_minutes"] = recommended_minutes

    def model(messages, info):
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model), output_type=LessonPlan, deps_type=LessonAgentRequest, retries=1
        )
        agent.output_validator(validate_plan)
        yield agent

    runner = PydanticLessonAgent(scope, "test-model")
    if accepted:
        assert runner.run(request).plan == plan
    else:
        with pytest.raises(LessonGenerationUnavailable):
            runner.run(request)
