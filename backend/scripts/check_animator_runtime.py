"""Verify local animator deployment without a provider call or paid generation."""

import subprocess
import tempfile
from pathlib import Path

from app.shared.infrastructure.settings import Settings


def main() -> None:
    config = Settings()
    tools = Path(config.animator_tools_directory).resolve()
    for name in (
        "package-lock.json",
        "validate-project.mjs",
        "Dockerfile",
        "template/package.json",
        "node_modules/canvaskit-wasm/bin/full/canvaskit.wasm",
    ):
        if not (tools / name).is_file():
            raise SystemExit(f"Missing animator runtime resource: {tools / name}")
    root = Path(config.animation_local_directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Creating files in the API is insufficient: the sibling worker must read
    # those exact host paths.
    with tempfile.TemporaryDirectory(prefix=".runtime-check-", dir=root) as directory:
        Path(directory, "probe").write_text("ready")
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--tmpfs=/tmp:rw,nosuid,size=64m",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--mount",
                f"type=bind,source={directory},target=/checks,readonly",
                config.animator_image,
                "node",
                "-e",
                "const fs = require('fs');"
                "if (fs.readFileSync('/checks/probe', 'utf8') !== 'ready') process.exit(1);"
                "require('/opt/animator/node_modules/typescript');"
                "fs.readFileSync('/opt/animator/validate-project.mjs');",
            ],
            check=True,
            timeout=60,
        )
    print("Animator ready: toolkit, worker image, Docker access, storage and offline rendering")


if __name__ == "__main__":
    main()
