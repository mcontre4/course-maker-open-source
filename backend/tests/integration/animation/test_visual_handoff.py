from dataclasses import replace

import pytest

from app.courses.adapters.ai.animation_project import project_digest
from app.courses.adapters.ai.visual_assets import stage_visual_assets
from app.courses.ports.animator import AnimationUnavailable

pytestmark = pytest.mark.integration


def test_stages_and_protects_the_exact_generated_asset_bundle(animation_files):
    request, job, _ = animation_files
    root = job.parent
    key = ".assets/" + "a" * 64 + "/assets"
    source = root / key
    source.mkdir(parents=True)
    (source / "pump.riv").write_bytes(b"RIVE-generated-test-asset")
    inputs = replace(request, asset_project_key=key, asset_output_hash=project_digest(source))
    protected = stage_visual_assets(inputs, job, root)
    relative = "remotion/public/illustrations/pump.riv"
    assert protected[relative] == (job / relative).read_bytes() == b"RIVE-generated-test-asset"
    (source / "pump.riv").write_bytes(b"changed after production")
    with pytest.raises(AnimationUnavailable, match="checksum"):
        stage_visual_assets(inputs, job, root)


def test_asset_handoff_rejects_an_external_project_reference(animation_files):
    request, job, _ = animation_files
    with pytest.raises(AnimationUnavailable, match="Invalid illustration"):
        stage_visual_assets(replace(request, asset_project_key="../outside"), job, job.parent)


def test_visual_repair_preserves_helpers_without_overwriting_the_new_scaffold(animation_files):
    request, job, protected = animation_files
    root = job.parent
    assets_key = ".assets/" + "a" * 64 + "/assets"
    assets = root / assets_key
    assets.mkdir(parents=True)
    (assets / "pump.riv").write_bytes(b"RIVE-test")
    previous_key = "b" * 64 + "/remotion"
    previous = root / previous_key
    (previous / "src/visuals").mkdir(parents=True)
    (previous / "src/visuals/Labels.tsx").write_text("export const Label = () => null;")
    (previous / "src/Root.tsx").write_text("old timeline scaffold must not be copied")
    inputs = replace(
        request,
        asset_project_key=assets_key,
        asset_output_hash=project_digest(assets),
        previous_project_key=previous_key,
    )
    stage_visual_assets(inputs, job, root)
    assert (
        job / "remotion/src/visuals/Labels.tsx"
    ).read_text() == "export const Label = () => null;"
    assert (job / "remotion/src/Root.tsx").read_bytes() == protected["remotion/src/Root.tsx"]
