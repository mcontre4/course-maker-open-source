import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { hasFinishedVideo, hasLessonArtifacts } from "./learning/lesson-view";
import type { RegenerationStart } from "./RegenerateMenu";

type LessonContent = StandaloneLessonResponse["content"];
type StageKey = RegenerationStart | "render";

export type LessonStage = Readonly<{
  key: StageKey;
  label: string;
  detail: string;
  saved: boolean;
  /** Reused unchanged by a regeneration that starts after this stage. */
  kept?: boolean;
}>;

/** A regeneration in flight: where it restarts and the content it started from. */
export type LessonRebuild = Readonly<{
  from: RegenerationStart;
  before: LessonContent;
}>;

export function lessonWorkflowStatus(lesson: StandaloneLessonResponse) {
  const { content, activeOperation, operationError } = lesson;
  if (activeOperation)
    return /automatic|video|animation|speech/.test(activeOperation)
      ? hasWatchableDraft(lesson)
        ? "Video ready · processing in background"
        : "Creating video"
      : /storyboard/.test(activeOperation)
        ? "Preparing script"
        : activeOperation === "plan"
          ? "Preparing outline"
          : "Saving changes";
  if (operationError) return "Needs attention";
  if (hasFinishedVideo(content))
    return content.animation?.reviewStatus === "skipped" ||
      content.animation?.reviewStatus === "warning"
      ? "Ready for your review"
      : "Video ready";
  if (content.animation)
    return "Preview available · video processing incomplete";
  if (lesson.playbackContent) return "Changes not in video yet";
  if (content.alignment) return "Narration saved · continue video";
  if (content.storyboard) return "Script ready";
  if (content.plan) return "Outline ready to review";
  return "Draft";
}

/** Colour family for the status pill: in progress, done, needs attention, or draft. */
export function lessonWorkflowTone(
  lesson: StandaloneLessonResponse,
): "working" | "ready" | "attention" | "draft" {
  if (lesson.activeOperation) return "working";
  if (lesson.operationError) return "attention";
  if (hasFinishedVideo(lesson.content)) return "ready";
  return "draft";
}

export function isFinishedLesson(lesson: StandaloneLessonResponse) {
  return (
    !lesson.activeOperation &&
    !lesson.operationError &&
    hasFinishedVideo(lesson.content)
  );
}

/** Every stage of an automatic run: the outline first, then the video pipeline. */
export function lessonAutomaticStages(
  lesson: StandaloneLessonResponse,
): LessonStage[] {
  return [
    {
      key: "outline",
      label: "Outline",
      detail: "Researching the topic and planning each part of the lesson",
      saved: !!lesson.content.plan,
    },
    ...lessonGenerationStages(lesson),
  ];
}

export function lessonGenerationStages(
  lesson: StandaloneLessonResponse,
): LessonStage[] {
  const { content } = lesson;
  const finished = hasFinishedVideo(content);
  return [
    {
      key: "script",
      label: "Script",
      detail: "Writing what the narrator says, scene by scene",
      saved: !!content.storyboard,
    },
    {
      key: "speech",
      label: "Narration",
      detail: "Recording the voice-over",
      saved: !!content.alignment,
    },
    {
      key: "animation",
      label: "Illustrations & animation",
      detail: "Drawing and animating each scene",
      saved: !!content.animation,
    },
    {
      key: "render",
      label: "Render & visual review",
      detail: "Producing the final video and checking it",
      saved: finished,
    },
  ];
}

const stageOutput: Record<StageKey, (content: LessonContent) => unknown> = {
  outline: (content) => content.plan,
  script: (content) => content.storyboard,
  speech: (content) => content.alignment,
  animation: (content) => content.animation,
  render: (content) => [content.videoUrl, content.animation],
};

/**
 * Stages of a regeneration: earlier stages are kept, and a rebuilt stage only
 * counts as saved once its output differs from what the run started with.
 */
export function lessonRebuildStages(
  lesson: StandaloneLessonResponse,
  rebuild: LessonRebuild,
): LessonStage[] {
  const stages =
    rebuild.from === "outline"
      ? lessonAutomaticStages(lesson)
      : lessonGenerationStages(lesson);
  const from = stages.findIndex((stage) => stage.key === rebuild.from);
  return stages.map((stage, index) =>
    index < from
      ? { ...stage, kept: true }
      : {
          ...stage,
          saved:
            stage.saved &&
            JSON.stringify(stageOutput[stage.key](lesson.content)) !==
              JSON.stringify(stageOutput[stage.key](rebuild.before)),
        },
  );
}

/**
 * Whether a run in progress has a new draft to watch while it finishes, rather
 * than only the finished video it is replacing.
 */
export function hasWatchableDraft(
  lesson: StandaloneLessonResponse,
  rebuild?: LessonRebuild,
) {
  const { content } = lesson;
  return (
    hasLessonArtifacts(content) &&
    !hasFinishedVideo(content) &&
    (!rebuild ||
      JSON.stringify(content.animation) !==
        JSON.stringify(rebuild.before.animation))
  );
}
