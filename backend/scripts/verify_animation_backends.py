"""Run a paid direct Fast/Luna video through the real HTTP pipeline."""

import argparse
import json
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from testcontainers.community.mysql import MySqlContainer
from testcontainers.community.redis import RedisContainer

from app.main import create_app
from app.shared.infrastructure.settings import Settings


def verify(
    env: Path,
    output: Path,
    backend: str,
    title: str,
    description: str,
) -> dict:
    started = time.monotonic()
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
            _env_file=env,
            database_url=database.get_connection_url(),
            redis_url=f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0",
            api_key="private-animation-backends-verification-2026",
            gcs_bucket=None,
            animator_tools_directory=str(repository / "tools/animator"),
            animation_local_directory=str(output / "animation"),
            speech_local_directory=str(output / "speech"),
            animator_image="course-maker-animator:canvas-v1",
            lesson_video_image="course-maker-renderer:canvas-v1",
            animator_timeout_sec=1800,
        )
        with TestClient(create_app(config)) as client:
            client.headers["Authorization"] = "Bearer private-animation-backends-verification-2026"
            response = client.post(
                "/api/v1/lessons",
                json={
                    "title": title,
                    "description": description,
                    "minutes": 1,
                    "generationMode": "fast",
                    "style": {
                        "visualStyleId": "flat-vector-science",
                        "reviewOutput": True,
                        "description": "Concise narration and three illustrated scenes.",
                        "audience": "Curious beginners",
                    },
                },
            )
            response.raise_for_status()
            lesson = response.json()
            identifier = lesson["id"]
            for stage in ("plan", "video"):
                print(f"{backend}: starting {stage}", flush=True)
                response = client.post(
                    f"/api/v1/lessons/{identifier}/{stage}",
                    json={
                        "expectedRevision": lesson["revision"],
                        "generationMode": "fast",
                        **(
                            {"message": description}
                            if stage == "plan"
                            else {
                                "animatorModel": "openai/gpt-6-luna:fast",
                                "animationBackend": backend,
                            }
                        ),
                    },
                )
                (output / f"{stage}.json").write_text(response.text)
                response.raise_for_status()
                lesson = response.json()
                print(f"{backend}: completed {stage}", flush=True)
            animation = lesson["content"]["animation"]
            assert animation["backend"] == backend
            assert animation["model"] == "openai/gpt-6-luna:fast"
            assert animation["reviewStatus"] in {"approved", "repaired"}
            playback = client.get(f"/api/v1/lessons/{identifier}/video")
            playback.raise_for_status()
            (output / "lesson.mp4").write_bytes(playback.content)
            partial = client.get(
                f"/api/v1/lessons/{identifier}/video", headers={"Range": "bytes=0-1023"}
            )
            assert partial.status_code == 206 and partial.content == playback.content[:1024]
            spend = client.get(f"/api/v1/lessons/{identifier}/spend")
            spend.raise_for_status()
            usage = spend.json()
            (output / "spend.json").write_text(json.dumps(usage, indent=2))
            visual_stages = {"animation", "visual_review", "animation_repair"}
            visual_usage = [row for row in usage["breakdown"] if row["stage"] in visual_stages]
            assert visual_usage and all(
                row["model"] == "openai/gpt-6-luna:fast" for row in visual_usage
            )
            stage_calls = {
                stage: sum(row["total"]["calls"] for row in visual_usage if row["stage"] == stage)
                for stage in visual_stages
            }
            assert stage_calls["animation"] >= 1 and stage_calls["visual_review"] >= 1
            if backend == "direct":
                assert stage_calls["animation"] == stage_calls["visual_review"] == 1
                assert stage_calls["animation_repair"] <= 1
                assert not list((output / "animation").glob("*/logs/codex-*.log"))
                assert not list((output / "animation/.reviews").glob("*/logs/visual-review.log"))
            cookies = dict(client.cookies)
        offline = config.model_copy(
            update={"openrouter_api_key": SecretStr(""), "elevenlabs_api_key": SecretStr("")}
        )
        with TestClient(create_app(offline)) as client:
            client.headers["Authorization"] = "Bearer private-animation-backends-verification-2026"
            client.cookies.update(cookies)
            restored = client.get(f"/api/v1/lessons/{identifier}")
            restored.raise_for_status()
            assert restored.json()["content"]["animation"] == animation
            restored_video = client.get(f"/api/v1/lessons/{identifier}/video")
            restored_video.raise_for_status()
            assert restored_video.content == playback.content
        result = {
            "backend": backend,
            "title": title,
            "animation": animation,
            "elapsed_sec": round(time.monotonic() - started, 2),
            "stage_calls": stage_calls,
            "total_spend": usage["total"],
            "range_playback": 206,
            "fresh_app_playback": True,
        }
        (output / "verification.json").write_text(json.dumps(result, indent=2))
        print(f"{backend}: verified {output / 'lesson.mp4'}", flush=True)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    verify(
        args.env_file,
        output / "direct",
        "direct",
        "How the Moon changes shape",
        "Explain the Moon reflecting sunlight, its orbit, and the changing illuminated "
        "portion visible from Earth. Distinguish phases from eclipses. "
        "Narration under 65 seconds, three concise scenes.",
    )


if __name__ == "__main__":
    main()
