"""Live stage-3 smoke test using a saved real lesson, isolated MySQL/Redis and real AI.

Never modifies the source database. Output artifacts contain course material;
choose a private output directory. Provider requests consume real credits.
"""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.community.mysql import MySqlContainer
from testcontainers.community.redis import RedisContainer

from app.courses.adapters.persistence.conversations import SqlAlchemySyllabusConversations
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.domain.identifiers import CourseId
from app.main import create_app
from app.shared.infrastructure.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config = Settings(_env_file=args.env_file)
    if not config.openrouter_api_key.get_secret_value():
        parser.error("The env file must configure OpenRouter credentials")
    source = create_engine(config.database_url)
    try:
        with Session(source) as session:
            course = MySqlCourseRepository(session).require_by_id(CourseId(args.course_id))
            conversation = SqlAlchemySyllabusConversations(session).get_by_course_id(course.id)
    finally:
        source.dispose()
    lesson = course.lesson(args.lesson_id)
    if lesson.plan is None or conversation is None or conversation.curriculum is None:
        parser.error("Select a course with a saved lesson plan and curriculum/guide")
    # Remove a previously saved storyboard only in the disposable copy.
    course = course._replace_lesson(
        replace(lesson, storyboard=None, storyboard_generation=None, alignment=None)
    )
    with (
        MySqlContainer("mysql:8.4", dialect="pymysql") as mysql,
        RedisContainer("redis:7.4") as redis,
    ):
        database_url = mysql.get_connection_url()
        engine = create_engine(database_url)
        try:
            migration = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            migration.attributes["database_url"] = database_url
            command.upgrade(migration, "head")
            with Session(engine) as session:
                MySqlCourseRepository(session).add(course)
                session.flush()
                SqlAlchemySyllabusConversations(session).save(
                    replace(conversation, revision=1),
                    0,
                )
                session.commit()
            live = config.model_copy(
                update={
                    "database_url": database_url,
                    "redis_url": f"redis://{redis.get_container_host_ip()}:"
                    f"{redis.get_exposed_port(6379)}/0",
                    "gcs_bucket": None,
                }
            )
            path = f"/api/v1/courses/{course.id}"
            headers = {"Authorization": f"Bearer {live.api_key.get_secret_value()}"}
            with TestClient(create_app(live), headers=headers) as client:
                response = client.post(
                    path + "/storyboards/generate", json={"lessonId": args.lesson_id}
                )
                assert response.status_code == 200, response.text
                payload = response.json()
            with Session(engine) as session:
                saved = (
                    MySqlCourseRepository(session).require_by_id(course.id).lesson(args.lesson_id)
                )
            board = saved.storyboard
            assert board is not None and saved.storyboard_generation is not None
            board.validate_plan(lesson.plan, lesson.minutes)
            assert saved.plan == lesson.plan
            # A fresh app must retrieve and reuse the result with credentials disabled.
            offline = live.model_copy(
                update={"openrouter_api_key": type(live.openrouter_api_key)("")}
            )
            with TestClient(create_app(offline), headers=headers) as client:
                retrieved = client.get(path + f"/lessons/{args.lesson_id}")
                assert retrieved.status_code == 200
                cached = client.post(
                    path + "/storyboards/generate", json={"lessonId": args.lesson_id}
                )
                assert cached.status_code == 200 and cached.json() == payload
                assert retrieved.json()["storyboard"]["scenes"][0]["narrationText"] == (
                    board.scenes[0].narration_text
                )
            args.output_dir.mkdir(parents=True, exist_ok=True)
            report = {
                "course_id": str(course.id),
                "lesson_id": args.lesson_id,
                "lesson_title": lesson.title,
                "target_minutes": lesson.minutes,
                "scenes": len(board.scenes),
                "cues": sum(len(s.cues) for s in board.scenes),
                "narration_words": sum(len(s.narration_text.split()) for s in board.scenes),
                "estimated_seconds": sum(s.target_duration_sec for s in board.scenes),
                "generation": asdict(saved.storyboard_generation),
                "checks": [
                    "real HTTP + provider + MySQL",
                    "source plan unchanged",
                    "domain/schema validation",
                    "fresh application retrieval",
                    "cached request with credentials disabled",
                ],
            }
            for filename, data in {
                "storyboard.json": asdict(board),
                "lesson-plan.json": asdict(lesson.plan),
                "course-guide.json": asdict(conversation.curriculum.guide),
                "report.json": report,
            }.items():
                (args.output_dir / filename).write_text(
                    json.dumps(data, indent=2, ensure_ascii=False)
                )
            print(json.dumps(report, indent=2))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
