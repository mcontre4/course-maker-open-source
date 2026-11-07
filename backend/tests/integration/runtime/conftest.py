import os
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fakes.lesson_agent import SuccessfulLessonAgent
from fastapi.testclient import TestClient
from fixtures.authenticated_client import authenticate_client
from sqlalchemy import create_engine, text
from testcontainers.community.mysql import MySqlContainer
from testcontainers.community.redis import RedisContainer

from app.main import create_app
from app.shared.infrastructure.settings import Settings


@pytest.fixture(scope="session")
def mysql_engine():
    database = yaml.safe_load((Path(__file__).parents[4] / "compose.yaml").read_text())["services"][
        "mysql"
    ]
    database_container = MySqlContainer(database["image"], dialect="pymysql")
    with database_container.with_command(database["command"]) as container:
        engine = create_engine(container.get_connection_url(), pool_pre_ping=True)
        config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
        config.attributes["database_url"] = engine.url.render_as_string(hide_password=False)
        command.upgrade(config, "head")
        yield engine
        engine.dispose()


@pytest.fixture
def clean_mysql(mysql_engine):
    with mysql_engine.begin() as connection:
        connection.execute(text("DELETE FROM standalone_lessons"))
        connection.execute(text("DELETE FROM courses"))
        connection.execute(text("DELETE FROM users"))
    return mysql_engine


@pytest.fixture(scope="session")
def redis_server():
    with RedisContainer("redis:7.4-alpine") as container:
        yield container


@pytest.fixture
def runtime_settings(clean_mysql, redis_server, tmp_path):
    return Settings(
        _env_file=None,
        database_url=clean_mysql.url.render_as_string(hide_password=False),
        redis_url=f"redis://{redis_server.get_container_host_ip()}:{redis_server.get_exposed_port(6379)}/0",
        api_key="integration-test-private-key-32-characters",
        auth_enabled=True,
        auth_public_url="http://localhost:5173",
        internal_tools_key="internal-integration-key-32-characters",
        openrouter_api_key="",
        tavily_api_key="",
        elevenlabs_api_key="",
        elevenlabs_usd_per_credit=None,
        speech_local_directory=str(tmp_path / "speech"),
    )


@pytest.fixture
def live_lesson_settings(runtime_settings):
    credentials = Settings(
        _env_file=os.environ["LESSON_TIMING_LIVE_ENV_FILE"],
        database_url=runtime_settings.database_url,
        api_key=runtime_settings.api_key,
    )
    assert credentials.openrouter_api_key.get_secret_value(), "OpenRouter is required"
    assert credentials.tavily_api_key.get_secret_value(), "Tavily is required"
    return runtime_settings.model_copy(
        update={
            "openrouter_api_key": credentials.openrouter_api_key,
            "tavily_api_key": credentials.tavily_api_key,
        }
    )


@pytest.fixture
def api(runtime_settings, request):
    config = runtime_settings.model_copy(
        update={"elevenlabs_usd_per_credit": getattr(request, "param", None)}
    )
    with TestClient(create_app(config)) as client:
        authenticate_client(client)
        client.headers["Authorization"] = "Bearer integration-test-private-key-32-characters"
        yield client


@pytest.fixture
def planned_lesson_api(runtime_settings):
    agent = SuccessfulLessonAgent()
    with TestClient(create_app(runtime_settings, lesson_agent=agent)) as client:
        authenticate_client(client)
        client.headers["Authorization"] = "Bearer integration-test-private-key-32-characters"
        yield client, agent


@pytest.fixture
def draft_payload():
    return {
        "style": {"visualStyleId": "flat-vector-science"},
        "title": "Python",
        "description": "Learn Python",
        "duration": {"mode": "weekly", "weeks": 2, "hoursPerWeek": 3},
    }


@pytest.fixture
def syllabus_payload():
    return {
        "chapters": [
            {
                "title": "Basics",
                "summary": "Begin here",
                "lessons": [
                    {
                        "title": "Variables",
                        "topics": ["Names"],
                        "minutes": 10,
                        "videoUrl": "https://example.com/lesson.mp4",
                        "quiz": [
                            {
                                "prompt": "Which names a variable?",
                                "options": ["x", "1"],
                                "answer": 0,
                                "explanation": "x is a name",
                            }
                        ],
                    }
                ],
            }
        ]
    }


@pytest.fixture
def service_account_info():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return {
        "type": "service_account",
        "project_id": "local-test",
        "private_key_id": "local",
        "private_key": pem,
        "client_email": "signer@local-test.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


@pytest.fixture
def generation_runtime(runtime_settings):
    from fakes.generation import GatedLessonAgent, GatedStoryboardAgent, GatedThumbnails

    lesson, script, thumbnail = GatedLessonAgent(), GatedStoryboardAgent(), GatedThumbnails()
    app = create_app(
        runtime_settings,
        lesson_agent=lesson,
        storyboard_agent=script,
        thumbnail_generator=thumbnail,
    )
    with TestClient(app) as client:
        authenticate_client(client)
        client.headers["Authorization"] = "Bearer integration-test-private-key-32-characters"
        try:
            yield client, lesson, script, thumbnail
        finally:
            for provider in (lesson, script, thumbnail):
                provider.gate.finish.set()
