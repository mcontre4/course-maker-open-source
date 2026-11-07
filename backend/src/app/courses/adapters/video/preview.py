"""Package validated Canvas source for isolated, provider-free browser playback."""

import base64
import json
import re
from pathlib import Path

from app.courses.adapters.ai.animation_project import project_digest
from app.courses.adapters.video.local import LocalLessonVideo
from app.courses.domain.animation import AnimationProject
from app.courses.ports.lesson_video import LessonVideoUnavailable


class LocalLessonPlayback:
    def __init__(self, directory: Path, videos: LocalLessonVideo) -> None:
        self._directory, self._videos = directory.resolve(), videos

    def video_ready(self, animation: AnimationProject) -> bool:
        return self._videos.read_ready(animation) is not None

    def preview(self, animation: AnimationProject) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}/javascript", animation.project_key):
            raise LessonVideoUnavailable("Live preview is available for Canvas animations")
        project = self._directory / animation.project_key
        try:
            if (
                not project.is_dir()
                or not project.resolve().is_relative_to(self._directory)
                or project.is_symlink()
                or any(p.is_symlink() for p in project.rglob("*"))
                or project_digest(project) != animation.output_hash
            ):
                raise LessonVideoUnavailable("The saved animation source is missing or invalid")
            timeline = json.loads((project / "timeline.json").read_text())
            # Only explicitly allowed project assets enter the sandbox. No URLs,
            # private inputs, provider credentials or filesystem paths are exposed.
            for scene in timeline["scenes"]:
                audio = scene["audio"]
                if not re.fullmatch(r"audio/[A-Za-z0-9_-]+\.wav", audio):
                    raise LessonVideoUnavailable("Invalid narration asset")
                scene["audio"] = self._data_uri(project / audio, "audio/wav")
            html = (project / "player.html").read_text()
            for font in (project / "fonts").glob("*.woff2"):
                html = html.replace("fonts/" + font.name, self._data_uri(font, "font/woff2"))
            for script in (
                "style/harness.js",
                "style/sound.js",
                "style/drawing.js",
                "animation.js",
                "player.js",
            ):
                source = (project / script).read_text()
                if script == "player.js":
                    source = source.replace(
                        'await (await fetch("timeline.json")).json()', json.dumps(timeline)
                    )
                source = re.sub(
                    r"</script",
                    lambda match: match.group().replace("</", r"<\/"),
                    source,
                    flags=re.IGNORECASE,
                )
                html = html.replace(
                    f'<script src="{script}"></script>', f"<script>{source}</script>"
                )
            bridge = Path(__file__).with_name("preview_bridge.js").read_text()
            html = html.replace("</body>", "<script>" + bridge + "</script></body>")
            return html
        except LessonVideoUnavailable:
            raise
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise LessonVideoUnavailable("Live preview could not be loaded") from exc

    @staticmethod
    def _data_uri(path: Path, mime: str) -> str:
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
