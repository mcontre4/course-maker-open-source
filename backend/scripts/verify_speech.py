"""Paid ElevenLabs end-to-end test in disposable MySQL/Redis with private local media.

Reads a saved course without modifying it. Optionally imports the exact storyboard
artifact produced by verify_storyboard.py into the disposable course copy.
"""

import argparse
import json
import wave
from dataclasses import asdict, replace
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr, TypeAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.community.mysql import MySqlContainer
from testcontainers.community.redis import RedisContainer

from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.domain.identifiers import CourseId
from app.courses.domain.storyboard import Storyboard
from app.main import create_app
from app.shared.infrastructure.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--storyboard", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config = Settings(_env_file=args.env_file)
    if not config.elevenlabs_api_key.get_secret_value():
        parser.error("Set COURSE_MAKER_ELEVENLABS_API_KEY in the selected env file")
    if args.storyboard:
        from app.courses.domain.course import Course
        from app.courses.domain.duration import Duration
        from app.courses.domain.identifiers import ChapterId, LessonId
        from app.courses.domain.lesson_plan import LessonPlan
        from app.courses.domain.syllabus import Chapter, Lesson

        board = TypeAdapter(Storyboard).validate_json(args.storyboard.read_bytes())
        plan = TypeAdapter(LessonPlan).validate_json(
            args.storyboard.with_name("lesson-plan.json").read_bytes()
        )
        concepts = tuple(dict.fromkeys(c for beat in plan.beats for c in beat.concepts))
        lesson = Lesson(
            LessonId(args.lesson_id),
            "Narration verification",
            concepts,
            board.target_video_minutes,
            plan=plan,
            storyboard=board,
        )
        course = Course(
            CourseId(args.course_id),
            "Speech verification",
            "Isolated stage-4 test",
            Duration("total", hours=1),
            chapters=(
                Chapter(
                    ChapterId("chapter_00000000-0000-0000-0000-000000000001"),
                    "Verification",
                    "Imported stage-3 artifacts",
                    (lesson,),
                ),
            ),
        ).approve()
    else:
        source = create_engine(config.database_url)
        try:
            with Session(source) as session:
                course = MySqlCourseRepository(session).require_by_id(CourseId(args.course_id))
        finally:
            source.dispose()
        lesson = course.lesson(args.lesson_id)
        board = lesson.storyboard
        if board is None or lesson.plan is None:
            parser.error("Select a planned lesson with a saved storyboard")
        course = course._replace_lesson(replace(lesson, alignment=None))
    assert lesson.plan is not None
    board.validate_plan(lesson.plan, lesson.minutes)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (
        MySqlContainer("mysql:8.4", dialect="pymysql") as mysql,
        RedisContainer("redis:7.4-alpine") as redis,
    ):
        engine = create_engine(mysql.get_connection_url())
        try:
            migration = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            migration.attributes["database_url"] = mysql.get_connection_url()
            command.upgrade(migration, "head")
            with Session(engine) as session:
                MySqlCourseRepository(session).add(course)
                session.commit()
            live = config.model_copy(
                update={
                    "database_url": mysql.get_connection_url(),
                    "redis_url": f"redis://{redis.get_container_host_ip()}:"
                    f"{redis.get_exposed_port(6379)}/0",
                    "gcs_bucket": None,
                    "speech_storage_backend": "local",
                    "speech_local_directory": str(output),
                }
            )
            path = f"/api/v1/courses/{course.id}"
            lesson_path = path + f"/lessons/{args.lesson_id}"
            headers = {"Authorization": f"Bearer {live.api_key.get_secret_value()}"}
            with TestClient(create_app(live), headers=headers) as client:
                response = client.post(path + "/speech/generate", json={"lessonId": args.lesson_id})
                assert response.status_code == 200, response.text
                payload = response.json()
                transcript = client.get(lesson_path + "/speech/transcript")
                assert transcript.status_code == 200
                assert transcript.text == "\n\n".join(s.narration_text for s in board.scenes)
            with Session(engine) as session:
                saved = (
                    MySqlCourseRepository(session).require_by_id(course.id).lesson(args.lesson_id)
                )
            assert saved.alignment is not None and saved.storyboard == board
            saved.alignment.validate_storyboard(board)
            offline = live.model_copy(update={"elevenlabs_api_key": SecretStr("")})
            with TestClient(create_app(offline), headers=headers) as client:
                cached = client.post(path + "/speech/generate", json={"lessonId": args.lesson_id})
                assert cached.status_code == 200, cached.text
                if cached.json() != payload:

                    def differences(left, right, path=""):
                        if isinstance(left, dict) and isinstance(right, dict):
                            return [
                                d
                                for key in left.keys() | right.keys()
                                for d in differences(left.get(key), right.get(key), f"{path}/{key}")
                            ]
                        if (
                            isinstance(left, list)
                            and isinstance(right, list)
                            and len(left) == len(right)
                        ):
                            return [
                                d
                                for i, (a, b) in enumerate(zip(left, right, strict=True))
                                for d in differences(a, b, f"{path}/{i}")
                            ]
                        return (
                            [] if left == right else [(path, repr(left)[:100], repr(right)[:100])]
                        )

                    raise AssertionError(differences(payload, cached.json())[:10])
                assert (
                    client.get(lesson_path).json()["alignment"]
                    == (payload["chapters"][0]["lessons"][0]["alignment"])
                )
                for scene in board.scenes:
                    audio = client.get(
                        lesson_path + "/speech/audio", params={"scene_id": scene.scene_id}
                    )
                    assert audio.status_code == 200 and audio.content.startswith(b"RIFF")
            # Convenient listening copy; the scene WAVs remain the production handoff.
            with wave.open(str(output / "lesson.wav"), "wb") as combined:
                combined.setnchannels(1)
                combined.setsampwidth(2)
                combined.setframerate(saved.alignment.settings.sample_rate)
                for index, scene in enumerate(saved.alignment.scenes):
                    if index:
                        combined.writeframes(
                            b"\x00\x00"
                            * round(
                                saved.alignment.silence_between_scenes_sec
                                * saved.alignment.settings.sample_rate
                            )
                        )
                    with wave.open(str(output / scene.audio_key), "rb") as audio:
                        combined.writeframes(audio.readframes(audio.getnframes()))
            with wave.open(str(output / "lesson.wav"), "rb") as combined:
                assert (
                    abs(
                        combined.getnframes() / combined.getframerate()
                        - saved.alignment.duration_sec
                    )
                    < 0.001
                )
            report = {
                "course_id": str(course.id),
                "lesson_id": args.lesson_id,
                "model": saved.alignment.settings.model_id,
                "scenes": len(saved.alignment.scenes),
                "words": sum(len(s.words) for s in saved.alignment.scenes),
                "cues": sum(len(s.cues) for s in saved.alignment.scenes),
                "measured_duration_sec": saved.alignment.duration_sec,
                "checks": [
                    "real ElevenLabs HTTP",
                    "measured WAV duration",
                    "exact narration",
                    "cue alignment",
                    "private local storage",
                    "combined listening WAV",
                    "transcript export",
                    "MySQL roundtrip",
                    "fresh application retrieval",
                    "cached POST with credentials disabled",
                ],
            }
            for name, value in {
                "storyboard.json": asdict(board),
                "alignment.json": asdict(saved.alignment),
                "report.json": report,
            }.items():
                (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False))
            (output / "transcript.txt").write_text(transcript.text)
            print(json.dumps(report, indent=2))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
