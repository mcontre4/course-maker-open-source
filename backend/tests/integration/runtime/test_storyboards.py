import json
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends
from fixtures.lesson_plan import lesson_plan
from fixtures.script import script_from_board, visual_output
from fixtures.storyboard import storyboard
from fixtures.syllabus import COURSE_ID, LESSON_ID, make_planned_course
from pydantic import SecretStr
from pydantic_ai.messages import ModelResponse, SystemPromptPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from sqlalchemy.orm import Session

from app.courses.adapters.ai.script import PydanticScriptAgent
from app.courses.adapters.ai.scripted_storyboard import ScriptedStoryboardAgent
from app.courses.adapters.ai.storyboard import PydanticStoryboardAgent
from app.courses.adapters.http.storyboards import get_storyboard_generator
from app.courses.adapters.persistence.conversations import SqlAlchemySyllabusConversations
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.generate_storyboard import GenerateStoryboard
from app.courses.composition import build_storyboard_agent
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import CourseId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.style import LessonStyle
from app.courses.ports.syllabus_agent import SyllabusConversation
from app.shared.infrastructure.database import get_session

pytestmark = pytest.mark.integration


def seed(engine):
    draft, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    course = draft.approve().plan_lesson(LESSON_ID, plan, PlanGeneration("test", 1, 0, 1))
    with Session(engine) as session:
        MySqlCourseRepository(session).add(course)
        session.flush()
        SqlAlchemySyllabusConversations(session).save(
            SyllabusConversation(COURSE_ID, 1, curriculum=curriculum),
            0,
        )
        session.commit()
    return plan


@pytest.mark.parametrize(
    "style_id",
    [
        "flat-vector-science",
        "watercolor-wash",
        "tech-glow",
        "whiteboard",
        "halftone-pop",
        "risograph",
        "gouache-poster",
        "soft-3d",
        "memphis",
        "bauhaus",
        "swiss-grid",
    ],
)
def test_http_agent_database_roundtrip_and_cache(api, clean_mysql, runtime_settings, style_id):
    plan = seed(clean_mysql)
    expected = storyboard(plan)
    calls = []
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    with Session(clean_mysql) as session:
        repository = MySqlCourseRepository(session)
        course = repository.require_by_id(CourseId(COURSE_ID))
        repository.save(replace(course, style=LessonStyle(visual_style_id=style_id)))
        session.commit()
    config = runtime_settings.model_copy(
        update={
            "openrouter_api_key": SecretStr("offline-style-reference"),
            "animator_tools_directory": str(tools),
        }
    )
    production = build_storyboard_agent(config, mode=GenerationMode.BALANCED)

    def model(messages, info):
        calls.append(messages)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    json.loads(
                        json.dumps(
                            asdict(script_from_board(expected))
                            if "segments"
                            in info.output_tools[0].parameters_json_schema["properties"]
                            else visual_output(expected)
                        )
                    ),
                )
            ]
        )

    @asynccontextmanager
    async def scope():
        async with production.visuals._scope() as agent:
            with agent.override(model=FunctionModel(model)):
                yield agent

    @asynccontextmanager
    async def script_scope():
        async with production.scripting._scope() as agent:
            with agent.override(model=FunctionModel(model)):
                yield agent

    def generator(session: Annotated[Session, Depends(get_session)]):
        return GenerateStoryboard(
            MySqlCourseRepository(session),
            SqlAlchemySyllabusConversations(session),
            ScriptedStoryboardAgent(
                PydanticScriptAgent(script_scope, "test-model"),
                PydanticStoryboardAgent(scope, "test-model"),
            ),
            CourseUnitOfWork(session),
        )

    production_generator = api.app.dependency_overrides[get_storyboard_generator]
    api.app.dependency_overrides[get_storyboard_generator] = generator
    path = f"/api/v1/courses/{COURSE_ID}"
    result = api.post(path + "/storyboards/generate", json={"lessonId": LESSON_ID})
    assert result.status_code == 200, result.text
    payload = result.json()["chapters"][0]["lessons"][0]["storyboard"]
    assert payload["scenes"][0]["narrationText"] == expected.scenes[0].narration_text
    assert payload["scenes"][0]["cues"][0]["anchorText"] == "Look at the name score"
    with Session(clean_mysql) as session:
        saved = MySqlCourseRepository(session).require_by_id(CourseId(COURSE_ID))
        assert saved.lesson(LESSON_ID).storyboard == expected
        assert saved.lesson(LESSON_ID).storyboard_generation.usage.model == "test-model"
    # Restore production DI: the cache must work even with disabled credentials.
    api.app.dependency_overrides[get_storyboard_generator] = production_generator
    cached = api.post(path + "/storyboards/generate", json={"lessonId": LESSON_ID})
    assert cached.status_code == 200, cached.text
    assert len(calls) == 2
    parts = [part for message in calls[1] for part in message.parts]
    prompts = "\n".join(part.content for part in parts if isinstance(part, SystemPromptPart))
    assert (tools / "styles" / style_id / "STYLE.md").read_text() in prompts
    prompt = next(part.content for part in parts if isinstance(part, UserPromptPart))
    inputs = json.loads(
        prompt
        if isinstance(prompt, str)
        else next(item for item in prompt if isinstance(item, str))
    )
    assert inputs["visual_style_id"] == style_id
    assert inputs["visual_style_version"] == 1
    assert inputs["script"] == json.loads(json.dumps(asdict(script_from_board(expected))))
    assert "plan" not in inputs
    assert saved.lesson(LESSON_ID).storyboard_generation.usage.requests == 2
    assert api.get(path + f"/lessons/{LESSON_ID}").json()["storyboard"] == payload


def test_missing_credentials_is_503_and_does_not_save(api, clean_mysql):
    seed(clean_mysql)
    path = f"/api/v1/courses/{COURSE_ID}"
    result = api.post(path + "/storyboards/generate", json={"lessonId": LESSON_ID})
    assert result.status_code == 503, result.text
    assert api.get(path + f"/lessons/{LESSON_ID}").json()["storyboard"] is None


@pytest.mark.parametrize(
    "body", [{}, {"lessonId": " "}, {"lessonId": 42}, {"lessonId": LESSON_ID, "visualStyle": " "}]
)
def test_rejects_bad_transport_input(api, body, clean_mysql):
    seed(clean_mysql)
    result = api.post(f"/api/v1/courses/{COURSE_ID}/storyboards/generate", json=body)
    assert result.status_code == 422
