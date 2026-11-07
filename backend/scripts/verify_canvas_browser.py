"""Verify real browser playback and review-policy changes with all paid providers disabled."""

import argparse
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from alembic import command
from alembic.config import Config
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


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--browser", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    parser.add_argument("--renderer-image", default="course-maker-renderer:canvas-v1")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    snapshot = args.snapshot.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = snapshot.parent
    api_port, ui_port = free_port(), free_port()
    key = "canvas-browser-verification-api-key-2026"
    with (
        MySqlContainer("mysql:8.4", dialect="pymysql") as database,
        RedisContainer("redis:7.4-alpine") as redis,
    ):
        migration = Config(str(repository / "backend/alembic.ini"))
        migration.set_main_option("script_location", str(repository / "backend/migrations"))
        migration.attributes["database_url"] = database.get_connection_url()
        command.upgrade(migration, "head")
        config = Settings(
            _env_file=None,
            database_url=database.get_connection_url(),
            redis_url=f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0",
            api_key=key,
            gcs_bucket=None,
            openrouter_api_key=SecretStr(""),
            elevenlabs_api_key=SecretStr(""),
            tavily_api_key=SecretStr(""),
            animation_local_directory=str(artifacts / "animation"),
            speech_local_directory=str(artifacts / "speech"),
            animator_tools_directory=str(repository / "tools/animator"),
            animator_image="course-maker-animator:canvas-v1",
            lesson_video_image=args.renderer_image,
        )
        server = uvicorn.Server(
            uvicorn.Config(create_app(config), host="127.0.0.1", port=api_port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        ui = None
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.1)
            api_url = f"http://127.0.0.1:{api_port}"
            with httpx.Client(
                base_url=api_url, headers={"Authorization": "Bearer " + key}
            ) as client:
                response = client.post(
                    "/api/v1/lessons",
                    json={
                        "title": "Browser session",
                        "description": "Verification",
                        "minutes": 1,
                        "style": {"visualStyleId": "flat-vector-science"},
                    },
                )
                response.raise_for_status()
                data = StandaloneLessonView.model_validate_json(snapshot.read_text()).model_dump()
                data["owner_id"] = response.json()["ownerId"]
                # HTTP alignment views omit private provider IDs and WAV hashes.
                source = artifacts / "animation" / data["content"]["animation"]["project_key"]
                private_inputs = json.loads((source.parent / "inputs.json").read_text())
                data["content"]["alignment"] = private_inputs["alignment"]
                data["content"]["storyboard"] = private_inputs["storyboard"]
                lesson = decode_standalone(data)
                engine = create_engine(config.database_url)
                with Session(engine) as session, session.begin():
                    SqlAlchemyStandaloneLessons(session).add(lesson)
                engine.dispose()
                cookies = [
                    {"name": k, "value": v, "domain": "127.0.0.1", "path": "/"}
                    for k, v in client.cookies.items()
                ]
            env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR"}}
            env.update(COURSE_MAKER_API_URL=api_url, COURSE_MAKER_API_KEY=key)
            with (output / "ui.log").open("w") as log:
                ui = subprocess.Popen(
                    ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(ui_port)],
                    cwd=repository / "frontend",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                script = repository / "tools/animator/tests/browser-delivery.cjs"
                subprocess.run(
                    [
                        "node",
                        str(script),
                        str(repository),
                        json.dumps(
                            {
                                "url": f"http://127.0.0.1:{ui_port}/lessons/{data['id']}",
                                "browser": args.browser,
                                "cookies": cookies,
                                "output": str(output),
                                "expectedHash": data["content"]["animation"]["output_hash"],
                                "expectedBackend": data["content"]["animation"].get(
                                    "backend", "direct"
                                ),
                            }
                        ),
                    ],
                    check=True,
                    timeout=180,
                )
        finally:
            if ui:
                import signal

                os.killpg(ui.pid, signal.SIGTERM)
                ui.wait(timeout=10)
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
