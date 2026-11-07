import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import {
  hasWatchableDraft,
  lessonAutomaticStages,
  lessonGenerationStages,
  lessonRebuildStages,
  type LessonRebuild,
} from "./lesson-workflow";
import type { RegenerationStart } from "./RegenerateMenu";

const rebuildScope: Record<RegenerationStart, string> = {
  outline:
    "Starting fresh with a new outline, script, narration and animation.",
  script: "Keeping your outline and rewriting everything after it.",
  speech: "Keeping your outline and script, and re-recording the voice-over.",
  animation: "Keeping the words and voice, and redrawing the visuals.",
};

export function LessonPipelineProgress({
  lesson,
  running,
  error,
  automatic = false,
  rebuild,
  actions,
}: {
  lesson: StandaloneLessonResponse;
  running: boolean;
  error?: unknown;
  /** An automatic run also covers the outline, so it is shown as the first stage. */
  automatic?: boolean;
  /** A regeneration in progress, so stages from its start are shown as rebuilding. */
  rebuild?: LessonRebuild;
  actions?: ReactNode;
}) {
  const all =
    rebuild && running
      ? lessonRebuildStages(lesson, rebuild)
      : automatic
        ? lessonAutomaticStages(lesson)
        : lessonGenerationStages(lesson);
  const rebuilding = running && !!rebuild;
  const stages = all.map((stage, index) =>
    running && index === all.length - 1 ? { ...stage, saved: false } : stage,
  );
  const current = stages.findIndex((stage) => !stage.saved);
  const failed = !running && !!(error || lesson.operationError);
  const fresh = current === 0 && !running && !failed;
  const playable = hasWatchableDraft(lesson, rebuild);
  const processing = lesson.spend?.steps
    ?.filter((s) => s.lessonId === lesson.id && s.finishedAt === null)
    .at(-1);
  const processingLabel =
    processing?.stage === "render"
      ? "Rendering and checking the video"
      : processing?.stage === "visual_review"
        ? "Reviewing the visuals"
        : processing?.stage === "animation_repair"
          ? "Applying visual corrections"
          : processing?.stage === "element_planning"
            ? "Identifying visual elements"
            : processing?.stage === "element_generation"
              ? "Building visual elements in parallel"
              : undefined;
  return (
    <section
      className="lesson-pipeline-progress"
      aria-label="Video generation progress"
      data-tone={failed ? "attention" : running ? "working" : "idle"}
    >
      <div className="pipeline-intro" role="status" aria-live="polite">
        <h2>
          {failed
            ? automatic
              ? "Your lesson needs another try."
              : "Video generation needs another try."
            : rebuilding && !playable
              ? "Regenerating your video"
              : automatic && running && !playable
                ? "Creating your lesson"
                : running
                  ? playable
                    ? "Your video is ready to watch"
                    : "Creating your lesson video"
                  : fresh
                    ? "Ready to create your video"
                    : "Your video draft is saved"}
        </h2>
        <p className="muted">
          {rebuilding && !playable ? (
            <>
              {rebuildScope[rebuild.from]} Your current video is kept until the
              new one is ready. You can leave this page and return from{" "}
              <Link to="/workspace">My creations</Link>.
            </>
          ) : running ? (
            playable ? (
              "You can play your lesson now. Rendering and visual review continue in the background."
            ) : (
              <>
                {automatic
                  ? "We’re going straight from your details to a finished video, with no review stops. This usually takes several minutes. "
                  : "This usually takes a few minutes. "}
                You can leave this page and return from{" "}
                <Link to="/workspace">My creations</Link>. Completed steps are
                saved.
              </>
            )
          ) : failed ? (
            "Something interrupted it partway through. Finished steps are saved, so retrying picks up where it stopped."
          ) : fresh ? (
            "We’ll write the script, record narration, animate, and render your lesson. Completed steps are saved along the way."
          ) : (
            "Continue from the saved work when you’re ready."
          )}
        </p>
        {running && processingLabel && (
          <p role="status" className="pipeline-current-stage">
            {processingLabel}…
          </p>
        )}
        {actions && <div className="pipeline-actions">{actions}</div>}
      </div>
      <ol className="pipeline-stages">
        {stages.map((stage, index) => {
          const state = stage.kept
            ? "kept"
            : stage.saved
              ? "saved"
              : index === current
                ? failed
                  ? "failed"
                  : running
                    ? "running"
                    : "next"
                : "waiting";
          return (
            <li key={stage.label} data-state={state}>
              <span className="pipeline-stage-symbol" aria-hidden="true">
                {stage.saved || stage.kept
                  ? "✓"
                  : state === "failed"
                    ? "!"
                    : index + 1}
              </span>
              <span className="pipeline-stage-copy">
                <span>{stage.label}</span>
                <small>{stage.detail}</small>
              </span>
              <strong>
                {stage.kept
                  ? "Kept"
                  : stage.saved
                    ? "Saved"
                    : state === "failed"
                      ? "Interrupted"
                      : state === "running"
                        ? "In progress"
                        : state === "next"
                          ? "Next"
                          : "Waiting"}
              </strong>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
