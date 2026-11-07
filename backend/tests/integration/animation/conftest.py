import shutil
from pathlib import Path

import pytest
from fakes.animation_worker import write_animation_source
from fakes.canvas import CanvasCommands, FakeCanvasAnimator
from fixtures.animation import animation_inputs


@pytest.fixture
def canvas_runtime(tmp_path):
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    commands = CanvasCommands(tools)
    inputs, _, _, _ = animation_inputs()
    animator = FakeCanvasAnimator(tmp_path, tools, "fake-key", command_runner=commands)
    return animator, commands, inputs, tmp_path


@pytest.fixture
def animation_files(tmp_path):
    from app.courses.adapters.ai.animation_project import stage

    inputs, _, _, _ = animation_inputs()
    tools = tmp_path / "tools"
    source = Path(__file__).resolve().parents[4] / "tools/animator/template"
    shutil.copytree(source, tools / "template", ignore=shutil.ignore_patterns("node_modules"))
    wasm = tools / "node_modules/canvaskit-wasm/bin/full/canvaskit.wasm"
    wasm.parent.mkdir(parents=True)
    wasm.write_bytes(b"Test CanvasKit resource")
    job = tmp_path / "job"
    protected = stage(inputs, job, tools)
    write_animation_source(inputs, job)
    return inputs, job, protected


@pytest.fixture
def direct_canvas_runtime(canvas_runtime, request):
    from dataclasses import replace

    import httpx
    from fakes.direct_animation import DirectAnimationProvider

    from app.courses.adapters.ai.direct_animation import DirectAnimationCall, DirectCanvasAnimator
    from app.courses.ports.animation_backend import AnimationBackend

    _, commands, inputs, root = canvas_runtime
    provider = DirectAnimationProvider()

    def clients():
        return httpx.Client(transport=httpx.MockTransport(provider))

    model = getattr(request, "param", "openai/gpt-6-luna")
    llm = DirectAnimationCall(clients, "test-key", model, "high")
    author = DirectCanvasAnimator(
        root, commands.tools, "test-key", model=model, llm=llm, command_runner=commands
    )
    return (
        author,
        provider,
        commands,
        replace(inputs, animation_backend=AnimationBackend.DIRECT),
        root,
    )
