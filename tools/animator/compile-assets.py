"""Compile untrusted, script-free RML offline and emit independently checked evidence."""
import hashlib
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

job = Path(sys.argv[1]).resolve()
root = job / "assets"
assert root.is_dir() and not any(p.is_symlink() for p in root.rglob("*")), "Unsafe assets"
manifest = json.loads((root / "manifest.json").read_text())
design = json.loads((root / "design-system.json").read_text())
assert all(k in design for k in ("palette", "typography", "spacing", "motion")), "Missing design tokens"
assert manifest.get("assets") and len(manifest["assets"]) <= 24, "Need 1–24 assets"
evidence = []
names = set()
for asset in manifest["assets"]:
    name = asset["id"]
    assert re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) and name not in names, "Invalid asset ID"
    names.add(name)
    assert asset.get("scene_ids") and asset.get("description") and asset.get("animation"), "Missing asset contract"
    source = root / "sources" / name
    assert source.is_dir(), "Missing Rive source"
    assert not any(p.suffix in {".luau", ".as", ".wgsl"} for p in source.rglob("*")), "Embedded scripts require signing"
    rml = list(source.glob("*.rml"))
    assert rml, "Missing RML"
    for path in rml:
        tree = ET.parse(path)
        for element in tree.iter():
            assert "Script" not in element.tag and "Shader" not in element.tag, "Script objects forbidden"
            for key, value in element.attrib.items():
                if key == "file":
                    assert (source / value).resolve().is_relative_to(source.resolve()), "External asset"
    # CLI captures otherwise play the first animation, which may be a static hold.
    # Point a dedicated preview state machine at the SAME named timeline used in Remotion.
    found = False
    for path in rml:
        tree = ET.parse(path)
        for board in tree.getroot().findall("Artboard"):
            for old in board.findall("StateMachine"):
                if old.get("name") == "Review timeline":
                    board.remove(old)
            timeline = next((a for a in board.iter("LinearAnimation")
                             if a.get("name") == asset["animation"]), None)
            if timeline is None:
                continue
            found = True
            timeline_id = timeline.get("id")
            assert timeline_id, "The named animation needs an ID"
            ids = {e.get("id") for e in tree.iter()}
            base = 1_000_000
            while any(f"0:{base+i}" in ids for i in range(4)):
                base += 4
            board.set("defaultStateMachineId", f"0:{base}")
            machine = ET.SubElement(board, "StateMachine", name="Review timeline", id=f"0:{base}")
            layer = ET.SubElement(machine, "StateMachineLayer", name="Review", id=f"0:{base+1}")
            entry = ET.SubElement(layer, "EntryState")
            ET.SubElement(entry, "StateTransition", stateToId=f"0:{base+2}")
            ET.SubElement(layer, "AnimationState", animationId=timeline_id, id=f"0:{base+2}")
        ET.indent(tree, space="  ")
        tree.write(path, encoding="unicode")
    assert found, f"Asset {name} has no LinearAnimation named {asset['animation']}"
    (source / "rive.yaml").write_text(f"name: {name}\n")
    for flag in ("--verify", "--once"):
        subprocess.run(["rive", str(source), flag, "--format=json"], check=True, timeout=90)
    binary = source / "build" / f"{name}.riv"
    content = binary.read_bytes()
    assert content.startswith(b"RIVE") and len(content) > 32, "Invalid Rive binary"
    (root / f"{name}.riv").write_bytes(content)
    samples = asset.get("review_times_sec", [0, 0.5, 1])
    assert 3 <= len(samples) <= 8 and all(isinstance(t, (int, float)) and math.isfinite(t) and 0 <= t <= 60 for t in samples), "Need 3–8 bounded motion samples"
    frames = []
    for index, seconds in enumerate(samples):
        png = job / "asset-review" / f"{name}-{index}.png"
        png.parent.mkdir(exist_ok=True)
        subprocess.run(["rive", str(source), f"--screenshot={png}", f"--advance={seconds}s"], check=True, timeout=90)
        frames.append(str(png.relative_to(job)))
    evidence.append({"id": name, "sha256": hashlib.sha256(content).hexdigest(), "frames": frames})
    # Keep editable sources; discard rebuild logs/binaries duplicated above.
    import shutil
    shutil.rmtree(source / "build")
files = [p for p in root.rglob("*") if p.is_file()]
assert len(files) <= 200 and sum(p.stat().st_size for p in files) < 50_000_000, "Asset budget exceeded"
(job / "asset-review/evidence.json").write_text(json.dumps(evidence, indent=2))
print("Rive assets compiled and motion samples rendered offline")
