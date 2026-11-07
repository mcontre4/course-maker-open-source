import json


class RecordingReviewCommands:
    """Exercise real file handoffs without calling paid render/review providers."""

    def __init__(self):
        self.calls = []
        self.review_arguments = []

    def __call__(self, job, kind, arguments, prompt, name):
        self.calls.append(name)
        timeline = json.loads((job / "remotion/src/timeline.json").read_text())
        if name == "render-review":
            output = job / "render"
            output.mkdir(exist_ok=True)
            (output / "contact-00.png").write_bytes(b"rendered contact sheet")
            (output / "lesson.mp4").write_bytes(b"rendered video")
            for scene in timeline["scenes"]:
                frame = min(
                    timeline["duration_frames"] - 1,
                    scene["start_frame"] + scene["duration_frames"] - 1,
                )
                (output / f"frame-{frame:06d}.png").write_bytes(b"rendered scene closing frame")
        else:
            assert name == "visual-review"
            self.review_arguments = arguments
            (job / "review.json").write_text(
                json.dumps(
                    {
                        "approved": True,
                        "feedback": "Readable connected mechanism",
                        "scene_checks": [
                            {
                                "scene_id": scene["scene_id"],
                                "observations": "Readable connected parts",
                            }
                            for scene in timeline["scenes"]
                        ],
                    }
                )
            )
