"""Verify code-first playback and background MP4 delivery with a saved real lesson."""

import argparse
import json
import os
import shutil
import signal
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
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--browser", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    parser.add_argument("--renderer-image", default="course-maker-renderer:canvas-v1")
    parser.add_argument(
        "--source-project",
        type=Path,
        help="Reuse an already generated Luna Fast result.json, with paid providers disabled",
    )
    args = parser.parse_args()
    if args.source_project is None and args.env_file is None:
        parser.error("Supply --env-file for fresh authoring, or --source-project to reuse code")
    repository = Path(__file__).resolve().parents[2]
    snapshot, output = args.snapshot.resolve(), args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    api_port, ui_port = free_port(), free_port()
    key = "live-playback-isolated-verification-key"
    with (
        MySqlContainer("mysql:8.4", dialect="pymysql") as database,
        RedisContainer("redis:7.4-alpine") as cache,
    ):
        migration = Config(str(repository / "backend/alembic.ini"))
        migration.set_main_option("script_location", str(repository / "backend/migrations"))
        migration.attributes["database_url"] = database.get_connection_url()
        command.upgrade(migration, "head")
        config = Settings(
            _env_file=None if args.source_project else args.env_file,
            database_url=database.get_connection_url(),
            redis_url=f"redis://{cache.get_container_host_ip()}:{cache.get_exposed_port(6379)}/0",
            api_key=key,
            gcs_bucket=None,
            speech_storage_backend="local",
            speech_local_directory=str(output / "speech"),
            animation_local_directory=str(output / "animation"),
            animator_tools_directory=str(repository / "tools/animator"),
            animator_image="course-maker-animator:canvas-v1",
            lesson_video_image=args.renderer_image,
            animator_timeout_sec=1800,
        )
        if args.source_project:
            config = config.model_copy(
                update={
                    "openrouter_api_key": SecretStr(""),
                    "elevenlabs_api_key": SecretStr(""),
                    "tavily_api_key": SecretStr(""),
                }
            )
        api_url = f"http://127.0.0.1:{api_port}"
        server = uvicorn.Server(
            uvicorn.Config(create_app(config), host="127.0.0.1", port=api_port, log_level="info")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        ui = None
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.1)
            with httpx.Client(
                base_url=api_url, headers={"Authorization": "Bearer " + key}
            ) as client:
                response = client.post(
                    "/api/v1/lessons",
                    json={
                        "title": "Verification session",
                        "description": "Code playback verification",
                        "minutes": 1,
                        "style": {"visualStyleId": "flat-vector-science"},
                    },
                )
                response.raise_for_status()
                data = StandaloneLessonView.model_validate_json(snapshot.read_text()).model_dump()
                data["owner_id"] = response.json()["ownerId"]
                saved_project = (
                    json.loads(args.source_project.read_text()) if args.source_project else None
                )
                if saved_project:
                    original_root = args.source_project.resolve().parent.parent
                    source = original_root / saved_project["project_key"]
                    if not source.exists():
                        original_root = original_root.parent
                        source = original_root / saved_project["project_key"]
                    destination = output / "animation" / saved_project["project_key"]
                    shutil.copytree(source, destination, dirs_exist_ok=True)
                    shutil.copyfile(
                        source.parent / "inputs.json", destination.parent / "inputs.json"
                    )
                else:
                    source = (
                        snapshot.parent / "animation" / data["content"]["animation"]["project_key"]
                    )
                private = json.loads((source.parent / "inputs.json").read_text())
                data["content"]["plan"] = private["plan"]
                data["content"]["alignment"] = private["alignment"]
                data["content"]["storyboard"] = private["storyboard"]
                # Reuse the real outline, script and WAVs, then exercise a fresh
                # explicit Luna Fast author through the actual browser controls.
                data["content"]["animation"] = (
                    {**saved_project, "review_status": "pending"} if saved_project else None
                )
                data["content"]["video_url"] = None
                data["content"]["previous_versions"] = []
                data["content"]["style"]["review_output"] = False
                shutil.copytree(
                    original_root.parent / "speech"
                    if saved_project
                    else snapshot.parent / "speech",
                    output / "speech",
                    dirs_exist_ok=True,
                )
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
                options = {
                    "url": f"http://127.0.0.1:{ui_port}/lessons/{data['id']}",
                    "browser": args.browser,
                    "cookies": cookies,
                    "output": str(output),
                    "reuseSource": bool(args.source_project),
                }
                print("Browser verification starting: " + options["url"], flush=True)
                subprocess.run(
                    [
                        "node",
                        str(repository / "tools/animator/tests/browser-live-playback.cjs"),
                        str(repository),
                        json.dumps(options),
                    ],
                    check=True,
                    timeout=2400,
                )
        finally:
            if ui:
                os.killpg(ui.pid, signal.SIGTERM)
                ui.wait(timeout=10)
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
