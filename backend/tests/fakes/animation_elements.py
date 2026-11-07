import json
from contextvars import ContextVar
from threading import Barrier, Lock

import httpx

from app.courses.ports.animation_elements import AnimationElementSpec, PreparedAnimationElement


class RecordingElementAgent:
    def __init__(self, events):
        self.events, self.requests = events, []
        self.specs = (AnimationElementSpec("car", "Car", "Whole car", "canvas", ("s01",)),)

    def generate(self, request):
        self.events.append("elements")
        self.requests.append(request)
        return tuple(PreparedAnimationElement(s, "function draw_car(ctx) {}") for s in self.specs)


class ParallelElementProvider:
    """All ten calls must overlap, without sleeps or monkey patching."""

    def __init__(self):
        self.requests, self.scopes = [], []
        self.scope = ContextVar("element_test_scope", default=None)
        self.barrier = Barrier(10, timeout=10)
        self.lock = Lock()
        self.invalid_plan = False
        self.invalid_source = False
        self.invalid_element_ids = set()

    def __call__(self, request):
        data = json.loads(request.content)
        with self.lock:
            self.requests.append(data)
            self.scopes.append(self.scope.get())
        context = json.loads(data["messages"][-1]["content"][0]["text"])
        if "assigned_element" not in context:
            elements = [
                {
                    "id": f"car_{i}",
                    "name": f"Car {i}",
                    "description": "One whole car",
                    "format": "svg" if i == 0 else "canvas",
                    "scene_ids": ["s01"],
                }
                for i in range(10)
            ]
            if self.invalid_plan:
                elements[1]["id"] = elements[0]["id"]
            output = json.dumps({"elements": elements})
        else:
            if self.barrier is not None:
                self.barrier.wait()
            spec = context["assigned_element"]
            output = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
                '<rect width="200" height="100" fill="red"/></svg>'
                if spec["format"] == "svg"
                else f"function draw_{spec['id']}(ctx) {{ ctx.fillRect(0,0,20,10); }}"
            )
            if (
                self.invalid_source
                and spec["format"] == "canvas"
                or spec["id"] in self.invalid_element_ids
            ):
                output = "window.explainer = () => {};"
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": output}}]}
        )
