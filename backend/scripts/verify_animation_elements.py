"""One real, private element/animation smoke run using saved narration and storyboard."""

import argparse
import json
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from pydantic import TypeAdapter

from app.courses.adapters.ai.animation_elements import StoryboardElementAgent
from app.courses.adapters.ai.animator import AnimationWorker
from app.courses.adapters.ai.canvas_delivery import CanvasDelivery
from app.courses.adapters.ai.direct_animation import DirectAnimationCall, DirectCanvasAnimator
from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.ports.animator import AnimationInput
from app.courses.ports.animator_model import AnimatorModel
from app.shared.infrastructure.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = Settings(
        _env_file=args.env_file.resolve(),
        database_url="postgresql+psycopg://unused:unused@localhost/unused",
    )
    tools = Path(__file__).resolve().parents[2] / "tools/animator"
    saved = json.loads(args.inputs.read_text())
    saved.update(
        audio=tuple(
            (args.inputs.parent / "javascript/audio" / (s["scene_id"] + ".wav")).read_bytes()
            for s in saved["alignment"]["scenes"]
        ),
        prepare_elements=True,
        review_output=False,
        existing_project=None,
        session=None,
        visual_feedback="",
        previous_project_key="",
        regeneration_key="element-smoke-v1",
    )
    request = TypeAdapter(AnimationInput).validate_python(saved)
    records: list[dict[str, Any]] = []
    lock = threading.Lock()
    started = time.perf_counter()

    class TimedCall(DirectAnimationCall):
        def _request(self, messages: list[dict[str, Any]], stage: str) -> str:
            start = time.perf_counter()
            try:
                return super()._request(messages, stage)
            finally:
                record = {
                    "stage": stage,
                    "start_sec": round(start - started, 3),
                    "duration_sec": round(time.perf_counter() - start, 3),
                }
                with lock:
                    records.append(record)
                    (output / "calls.json").write_text(json.dumps(records, indent=2))
                    print(json.dumps(record), flush=True)

    def clients() -> httpx.Client:
        return httpx.Client(timeout=httpx.Timeout(config.animator_timeout_sec, connect=15))

    model = AnimatorModel.SONNET.value
    key = config.openrouter_api_key.get_secret_value()
    llm = TimedCall(clients, key, model, "low")
    elements = TimedCall(clients, key, model, "low", max_output_tokens=16000)
    author = DirectCanvasAnimator(
        output,
        tools,
        key,
        model,
        config.animator_image,
        config.animator_timeout_sec,
        llm=llm,
    )
    renderer = AnimationWorker(
        output, tools, "", model, config.lesson_video_image, config.animator_timeout_sec
    )
    # Review is disabled for this lightweight run; the real renderer still validates delivery.
    delivery = CanvasDelivery(
        output, [], renderer.run_job, renderer.run_job, config.lesson_video_image
    )
    production = ProduceCanvasAnimation(
        author,
        delivery,
        StoryboardElementAgent(output, tools, elements),
    )
    project = production.execute(ProduceCanvasAnimationRequest(request)).project
    generated = json.loads((output / project.input_hash / "inputs.json").read_text())
    report = {
        "saved_inputs": str(args.inputs.resolve()),
        "model": model,
        "duration_sec": project.duration_sec,
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "elements": [e["spec"] for e in generated["prepared_elements"]],
        "calls": records,
        "project": asdict(project),
    }
    (output / "verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
