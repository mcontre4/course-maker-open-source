import json

import httpx


class DirectAnimationProvider:
    """Recording HTTP boundary with explicit model outputs, without SDK retries."""

    def __init__(self):
        self.requests = []
        self.outputs = []
        self.finish_reason = "stop"
        self.status = 200
        self.error_response = None
        self.connection_failure = False

    def __call__(self, request):
        self.requests.append(json.loads(request.content))
        if self.connection_failure:
            raise httpx.RemoteProtocolError("Upstream connection closed")
        if self.error_response is not None:
            return httpx.Response(self.status, json={"error": self.error_response})
        return httpx.Response(
            self.status,
            json={
                "id": "gen_direct_test",
                "choices": [
                    {
                        "finish_reason": self.finish_reason,
                        "message": {"content": self.outputs.pop(0)},
                    }
                ],
            },
        )
