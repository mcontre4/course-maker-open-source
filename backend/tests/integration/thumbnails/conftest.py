import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


@pytest.fixture
def thumbnail_server():
    @contextmanager
    def serve(svg=None, status=200, finish_reason="stop", response_body=None):
        calls = []
        illustration = (
            svg
            if svg is not None
            else (
                Path(__file__).parents[3]
                / "src/app/courses/adapters/ai/thumbnail_examples/inertia.svg"
            ).read_text()
        )

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                payload = json.dumps(
                    response_body
                    if response_body is not None
                    else {
                        "choices": [
                            {
                                "finish_reason": finish_reason,
                                "message": {"content": illustration},
                            }
                        ]
                    }
                ).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", calls
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    return serve


@pytest.fixture(scope="session")
def thumbnail_database():
    from sqlalchemy import create_engine
    from testcontainers.community.postgres import PostgresContainer

    from app.courses.adapters.persistence.models import CourseRecord
    from app.courses.adapters.persistence.spend import GenerationStepRecord, ModelChargeRecord
    from app.courses.adapters.persistence.standalone import StandaloneLessonRecord
    from app.shared.infrastructure.database import Base

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url())
        Base.metadata.create_all(
            engine,
            tables=[
                CourseRecord.__table__,
                StandaloneLessonRecord.__table__,
                ModelChargeRecord.__table__,
                GenerationStepRecord.__table__,
            ],
        )
        try:
            yield engine
        finally:
            engine.dispose()
