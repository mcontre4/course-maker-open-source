import json
import subprocess

from app.courses.adapters.ai.canvas_animator import CanvasAnimator
from app.courses.ports.animator import AnimationUnavailable
from app.courses.ports.visual_production import VisualReview


class RecordingDelivery:
    def __init__(self, on_deliver=lambda project: None):
        self.on_deliver = on_deliver
        self.calls = []
        self.decisions = [VisualReview(True, "Good illustration and continuity")]
        self.repair_feedback = []

    def deliver(self, project, *, review, repair_feedback=None, source_ready=None):
        self.on_deliver(project)
        self.calls.append((project, review))
        self.repair_feedback.append(repair_feedback)
        decision = self.decisions.pop(0)
        if isinstance(decision, Exception):
            raise decision
        if decision.approved and source_ready is not None:
            source_ready()
        return decision


class CanvasCommands:
    """Real source-validator subprocess and filesystem; fake paid author/render boundaries."""

    def __init__(self, tools):
        self.tools = tools
        self.calls = []
        self.bad_quality = False
        self.review_findings = False
        self.change_on_repair = False
        self.change_on_author = False
        self.tamper = False
        self.fail_author_once = False
        self.authoring_round = 0
        self.review_override = None
        self.invalid_source = False
        self.fail_final_once = False
        self.reviewer_writes_video = False
        self.omit_closing_frames = False

    def __call__(self, job, kind, arguments, prompt, name):
        self.calls.append(name)
        if name.startswith(("author-", "repair-")):
            self.authoring_round += 1
            if (
                name.startswith("repair-")
                and self.change_on_repair
                or name.startswith("author-")
                and self.change_on_author
            ):
                (job / "change-request.json").write_text(
                    json.dumps(
                        {
                            "scene_ids": ["s01"],
                            "reason": "Missing sourced map data",
                            "requested_change": "Provide geographic data",
                        }
                    )
                )
                return
            style_id = json.loads((job / "inputs.json").read_text())["visual_style_id"]
            drawing = {
                "flat-vector-science": "FV.sky(ctx,W,H,t);",
                "watercolor-wash": (
                    "ctx.fillStyle='rgb('+WC.PAPER.join(',')+')';ctx.fillRect(0,0,W,H);"
                ),
                "tech-glow": "TG.background(ctx,W,H,t);",
                "whiteboard": "WB.background(ctx,W,H,t);",
                "halftone-pop": ("const p=HP.plates(W,H);HP.composite(ctx,p.col,p.key,W,H);"),
                "risograph": "RISO.composite(ctx,RISO.plates(W,H,t),W,H,t);",
                "gouache-poster": "GP.frame(W,H).commit(ctx);",
                "soft-3d": "CLAY.background(ctx,W,H,t);",
                "memphis": "MEMPHIS.background(ctx,W,H);",
                "bauhaus": "BAUHAUS.composite(ctx,BAUHAUS.plates(W,H),W,H);",
                "swiss-grid": "SWISS.composite(ctx,SWISS.frame(W,H),W,H);",
            }[style_id]
            (job / "javascript/animation.js").write_text(
                "window.explainer=(ctx,W,H,t)=>{" + drawing + "};"
                "window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];"
                + f"// authoring round {self.authoring_round}"
            )
            if self.invalid_source:
                (job / "javascript/animation.js").write_text("window.explainer = (")
            if self.tamper:
                (job / "javascript/style/drawing.js").write_text("modified")
            if self.fail_author_once:
                self.fail_author_once = False
                (job / "javascript/style/drawing.js").write_text("unfinished trusted edit")
                (job / "javascript/unexpected.js").write_text("unfinished extra output")
                (job / "change-request.json").write_text("unfinished change request")
                raise AnimationUnavailable("Interrupted authoring worker")
        elif name.startswith("validate-"):
            subprocess.run(
                ["node", str(self.tools / "validate-canvas.mjs"), str(job / "javascript")],
                check=True,
                capture_output=True,
            )
        elif name in {"render-review", "render-final"}:
            output = job / "render"
            output.mkdir(exist_ok=True)
            if arguments[-1] != "review":
                (output / "lesson.mp4").write_bytes(b"rendered-canvas-video")
            (output / "verification.json").write_text('{"deterministic": true}')
            (output / "visual-plan.json").write_text("[]")
            (output / "contact-00.png").write_bytes(b"rendered-key-frames")
            (output / "motion-00.png").write_bytes(b"rendered-motion-strip")
            if not self.omit_closing_frames:
                timeline = json.loads((job / "javascript/timeline.json").read_text())
                for scene in timeline["scenes"]:
                    closing = min(
                        timeline["duration_frames"] - 1,
                        scene["start_frame"] + scene["duration_frames"] - 1,
                    )
                    (output / f"frame-{closing:06d}.png").write_bytes(b"rendered-closing-frame")
            if name == "render-final" and self.fail_final_once:
                self.fail_final_once = False
                (output / "lesson.mp4").write_bytes(b"incomplete-encode")
                raise AnimationUnavailable("Final encoder interrupted")
        elif name == "visual-review":
            if self.reviewer_writes_video:
                (job / "render/lesson.mp4").write_bytes(b"unvalidated-video")
            timeline = json.loads((job / "javascript/timeline.json").read_text())
            (job / "review.json").write_text(
                json.dumps(
                    {
                        "approved": not self.review_findings,
                        "feedback": "Clear illustrations and flowing explanations",
                        "scene_checks": [
                            {
                                "scene_id": s["scene_id"],
                                "observations": "Readable topic-specific artwork",
                            }
                            for s in timeline["scenes"]
                        ],
                        "quality": {
                            key: 2 if self.bad_quality else 4
                            for key in (
                                "style_fidelity",
                                "illustration",
                                "composition",
                                "continuity",
                                "explanation",
                                "visual_development",
                                "pacing",
                            )
                        },
                    }
                )
            )
            if self.review_override is not None:
                (job / "review.json").write_text(json.dumps(self.review_override))


class FakeCanvasAnimator(CanvasAnimator):
    def _authoring_identity(self, prompt_file):
        return ["fake-author", self._model, self._reasoning_effort, prompt_file]

    def _author(self, job, prompt_file, prompt, name):
        self._execute(job, "author", [], prompt, name)
