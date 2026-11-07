"""Paid Fast-mode verification of plain-JavaScript generation and both review settings."""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.community.mysql import MySqlContainer
from testcontainers.community.redis import RedisContainer

from app.courses.adapters.http.standalone import StandaloneLessonView
from app.courses.adapters.persistence.standalone import (
    SqlAlchemyStandaloneLessons,
    decode_standalone,
)
from app.main import create_app
from app.shared.infrastructure.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", type=Path, help="Resume a saved self-review lesson")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    repository = Path(__file__).resolve().parents[2]
    with (
        MySqlContainer("mysql:8.4", dialect="pymysql") as database,
        RedisContainer("redis:7.4-alpine") as redis,
    ):
        migration = Config(str(repository / "backend/alembic.ini"))
        migration.set_main_option("script_location", str(repository / "backend/migrations"))
        migration.attributes["database_url"] = database.get_connection_url()
        command.upgrade(migration, "head")
        config = Settings(
            _env_file=args.env_file,
            database_url=database.get_connection_url(),
            redis_url=f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0",
            api_key="private-canvas-verification-api-key-2026",
            gcs_bucket=None,
            animator_tools_directory=str(repository / "tools/animator"),
            animation_local_directory=str(output / "animation"),
            speech_local_directory=str(output / "speech"),
            animator_image="course-maker-animator:canvas-v1",
            lesson_video_image="course-maker-renderer:canvas-v1",
            animator_timeout_sec=1800,
        )
        with TestClient(create_app(config)) as client:
            client.headers["Authorization"] = "Bearer private-canvas-verification-api-key-2026"
            preferences = {
                "visualStyleId": "flat-vector-science",
                "reviewOutput": False,
                "description": "Curious, concise and clear. Match the Silk Roads vector reference.",
                "audience": "Curious beginners",
            }
            response = client.post(
                "/api/v1/lessons",
                json={
                    "title": "How the Silk Roads connected cultures",
                    "description": "Explain the history of the Silk Roads in about one minute. "
                    "Show a schematic route network, Han expansion in the second century BCE, "
                    "caravans exchanging silk and other goods, the movement of ideas, and the "
                    "lasting connection between cultures. Three concise narration segments with "
                    "continuous visuals. No invented measurements or literal border maps.",
                    "minutes": 1,
                    "generationMode": "fast",
                    "style": preferences,
                },
            )
            response.raise_for_status()
            lesson = response.json()
            identifier = lesson["id"]
            stages = ("plan", "approve", "storyboard", "speech", "animation")
            if args.resume:
                data = StandaloneLessonView.model_validate_json(
                    args.resume.read_text()
                ).model_dump()
                data["owner_id"] = lesson["ownerId"]
                source = output / "animation" / data["content"]["animation"]["project_key"]
                private = json.loads((source.parent / "inputs.json").read_text())
                data["content"]["alignment"] = private["alignment"]
                data["content"]["storyboard"] = private["storyboard"]
                restored_lesson = decode_standalone(data)
                engine = create_engine(config.database_url)
                with Session(engine) as session, session.begin():
                    SqlAlchemyStandaloneLessons(session).add(restored_lesson)
                engine.dispose()
                identifier = data["id"]
                response = client.get(f"/api/v1/lessons/{identifier}")
                response.raise_for_status()
                lesson = response.json()
                saved_style = lesson["content"]["style"]
                preferences = {
                    "visualStyleId": saved_style["visualStyleId"],
                    "reviewOutput": saved_style["reviewOutput"],
                    "description": saved_style["request"],
                    "audience": saved_style["audience"],
                    "voiceId": saved_style["requestedVoiceId"],
                }
                stages = ()
                print("Resumed real Fast lesson, script and measured speech", flush=True)
            else:
                (output / "draft.json").write_text(json.dumps(lesson, indent=2))
            frozen_narration = (
                [s["narrationText"] for s in lesson["content"]["storyboard"]["scenes"]]
                if lesson["content"]["storyboard"] is not None
                else None
            )
            for stage in stages:
                print(f"Starting real Fast stage: {stage}", flush=True)
                payload = {"expectedRevision": lesson["revision"], "generationMode": "fast"}
                if stage == "plan":
                    payload["message"] = lesson["description"]
                response = client.post(f"/api/v1/lessons/{identifier}/{stage}", json=payload)
                if response.status_code != 200:
                    (output / f"{stage}-failure.txt").write_text(response.text)
                    raise RuntimeError(f"Stage {stage} failed: {response.status_code}")
                lesson = response.json()
                if stage == "storyboard":
                    frozen_narration = [
                        s["narrationText"] for s in lesson["content"]["storyboard"]["scenes"]
                    ]
                elif frozen_narration is not None:
                    assert [
                        s["narrationText"] for s in lesson["content"]["storyboard"]["scenes"]
                    ] == frozen_narration, f"Frozen narration changed during {stage}"
                (output / f"{stage}.json").write_text(json.dumps(lesson, indent=2))
                print(f"Completed {stage}", flush=True)
            animation = lesson["content"]["animation"]
            assert frozen_narration is not None
            assert animation["reviewStatus"] == "skipped"
            assert animation["projectKey"].endswith("/javascript")
            assert not (output / "animation/.assets").exists()
            if not args.resume:
                assert not list((output / "animation/.reviews").glob("*/logs/visual-review.log"))
            response = client.get(f"/api/v1/lessons/{identifier}/video")
            response.raise_for_status()
            (output / "self-review.mp4").write_bytes(response.content)
            partial = client.get(
                f"/api/v1/lessons/{identifier}/video", headers={"Range": "bytes=0-1023"}
            )
            assert partial.status_code == 206 and partial.content == response.content[:1024]
            original_alignment = lesson["content"]["alignment"]
            preferences["reviewOutput"] = True
            response = client.post(
                f"/api/v1/lessons/{identifier}/style",
                json={
                    "style": preferences,
                    "expectedVersion": lesson["content"]["style"]["version"],
                    "generationMode": "fast",
                },
            )
            response.raise_for_status()
            lesson = response.json()
            assert lesson["content"]["alignment"] == original_alignment
            print("Starting final AI review with original narration", flush=True)
            response = client.post(
                f"/api/v1/lessons/{identifier}/animation",
                json={
                    "expectedRevision": lesson["revision"],
                    "generationMode": "fast",
                },
            )
            if response.status_code != 200:
                (output / "review-failure.txt").write_text(response.text)
                raise RuntimeError(f"AI review failed: {response.status_code}")
            lesson = response.json()
            review_status = lesson["content"]["animation"]["reviewStatus"]
            assert review_status in {"approved", "repaired"}, review_status
            assert lesson["content"]["alignment"] == original_alignment
            assert [s["narrationText"] for s in lesson["content"]["storyboard"]["scenes"]] == (
                frozen_narration
            )
            response = client.get(f"/api/v1/lessons/{identifier}/video")
            response.raise_for_status()
            (output / "lesson.mp4").write_bytes(response.content)
            (output / "final.json").write_text(json.dumps(lesson, indent=2))
            # Fresh app reload with paid providers disabled must retain playback.
            cookies = dict(client.cookies)
        config = config.model_copy(
            update={"openrouter_api_key": SecretStr(""), "elevenlabs_api_key": SecretStr("")}
        )
        with TestClient(create_app(config)) as fresh:
            fresh.headers["Authorization"] = "Bearer private-canvas-verification-api-key-2026"
            fresh.cookies.update(cookies)
            restored = fresh.get(f"/api/v1/lessons/{identifier}")
            restored.raise_for_status()
            assert restored.json()["content"]["animation"] == lesson["content"]["animation"]
            assert [
                s["narrationText"] for s in restored.json()["content"]["storyboard"]["scenes"]
            ] == frozen_narration
            playback = fresh.get(f"/api/v1/lessons/{identifier}/video")
            playback.raise_for_status()
            assert playback.content == response.content
        (output / "verification.json").write_text(
            json.dumps(
                {
                    "generation_mode": "fast",
                    "lesson_id": identifier,
                    "review_modes": ["skipped", review_status],
                    "narration_preserved": True,
                    "range_playback": 206,
                    "fresh_app_playback": True,
                    "animation": lesson["content"]["animation"],
                },
                indent=2,
            )
        )
        print(
            f"Verified both review modes and persistent playback: {output / 'lesson.mp4'}",
            flush=True,
        )


if __name__ == "__main__":
    main()
