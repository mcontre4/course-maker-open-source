"""A local HTTP provider implementing the ElevenLabs wire contract; never makes paid calls."""

import base64
import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


@contextmanager
def elevenlabs_server(
    *, status=200, invalid=None, chunk_durations=None, error_body=None, strip_delivery=False
):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers.get("xi-api-key"), body))
            text = body["inputs"][0]["text"]
            if strip_delivery and text.startswith("["):
                text = text.split("] ", 1)[1]
            duration = chunk_durations[len(requests) - 1] if chunk_durations else len(text) / 100
            data = {
                "audio_base64": base64.b64encode(b"\x01\x00" * round(24000 * duration)).decode(),
                "alignment": {
                    "characters": list(text),
                    "character_start_times_seconds": [
                        round(i * duration / len(text), 9) for i in range(len(text))
                    ],
                    "character_end_times_seconds": [
                        round((i + 1) * duration / len(text), 9) for i in range(len(text))
                    ],
                },
            }
            if invalid == "missing":
                data["alignment"] = None
            elif invalid == "base64":
                data["audio_base64"] = "not-base64"
            elif invalid == "length":
                data["alignment"]["characters"].pop()
            elif invalid == "timing":
                # Corrupt spoken text, not an optional nonspoken delivery instruction.
                spoken_start = text.index("] ") + 2 if text.startswith("[") and "] " in text else 0
                data["alignment"]["character_end_times_seconds"][spoken_start] = 1000000
            elif invalid == "punctuation":
                data["alignment"]["character_end_times_seconds"][-1] += 0.08
            elif invalid == "audio":
                data["audio_base64"] = base64.b64encode(b"odd").decode()
            payload = json.dumps(error_body if error_body is not None else data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("request-id", "local-provider-request")
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
