import json
from contextlib import contextmanager
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from app.courses.domain.style import LessonStyle


@pytest.fixture
def style_server():
    @contextmanager
    def serve(*, voice_status=200, invalid=False, model_status=200):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                calls.append((self.path, None))
                if voice_status != 200:
                    return self.respond(voice_status, {"detail": {"status": "missing_permissions"}})
                page_two = "next_page_token=page2" in self.path
                return self.respond(
                    200,
                    {
                        "voices": [
                            {
                                "voice_id": "steady" if page_two else "friendly",
                                "name": "Steady" if page_two else "Friendly",
                                "description": "Educational narrator",
                                "sharing": None,
                                "labels": {"language": "en"},
                                "preview_url": "https://example.com/sample.mp3",
                            }
                        ],
                        "has_more": not page_two,
                        "next_page_token": None if page_two else "page2",
                    },
                )

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                return self.respond(
                    model_status,
                    {
                        "id": "generation_style",
                        "usage": {"cost": 0.0001},
                        "choices": [
                            {
                                "message": {
                                    "content": "{}"
                                    if invalid
                                    else json.dumps(
                                        asdict(
                                            LessonStyle(
                                                summary="Warm, clear teaching.",
                                                voice_id="friendly",
                                                delivery="Warm, reassuring",
                                            )
                                        )
                                    )
                                }
                            }
                        ],
                    },
                )

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", calls
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    return serve
