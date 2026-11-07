import {
  LessonInteractiveError,
  briefProblem,
  changeProblem,
  detailsProblem,
  tidyDetails,
  type InteractiveDetails,
  type LearnerInteractive,
  type LessonInteractive,
} from "../domain/lesson-interactive";
import type { GenerationMode } from "./generation-mode";

export type {
  InteractiveBuildStage,
  InteractiveDetails,
  InteractiveLessonContext,
  InteractiveState,
  InteractiveVersion,
  LearnerInteractive,
  LessonInteractive,
} from "../domain/lesson-interactive";
// The interface layer reaches interactive rules through the application boundary.
export {
  LessonInteractiveError,
  briefProblem,
  changeProblem,
  detailsProblem,
  interactiveBuildStages,
  interactiveIdeas,
  interactiveLimits,
  interactiveState,
  learnerView,
} from "../domain/lesson-interactive";

export type InteractiveRef = Readonly<{ lessonId: string; id: string }>;

/** Where interactives are built and kept. Builds run in the background. */
export interface LessonInteractiveBackend {
  list(lessonId: string): Promise<readonly LessonInteractive[]>;
  get(ref: InteractiveRef): Promise<LessonInteractive>;
  create(request: {
    lessonId: string;
    brief: string;
    generationMode?: GenerationMode;
  }): Promise<LessonInteractive>;
  requestChange(
    request: InteractiveRef & { instruction: string; expectedRevision: number },
  ): Promise<LessonInteractive>;
  retryBuild(ref: InteractiveRef): Promise<LessonInteractive>;
  cancelBuild(ref: InteractiveRef): Promise<LessonInteractive>;
  saveDetails(
    request: InteractiveRef & {
      details: InteractiveDetails;
      expectedRevision: number;
    },
  ): Promise<LessonInteractive>;
  restoreVersion(
    request: InteractiveRef & { version: number; expectedRevision: number },
  ): Promise<LessonInteractive>;
  /** Choose the version learners get; null takes it out of the lesson. */
  setPublishedVersion(
    request: InteractiveRef & { version: number | null },
  ): Promise<LessonInteractive>;
  reorder(
    lessonId: string,
    orderedIds: readonly string[],
  ): Promise<readonly LessonInteractive[]>;
  remove(ref: InteractiveRef): Promise<void>;
}

export type LessonInteractiveApplication = LessonInteractiveBackend;

/** Applies creator-facing rules before anything reaches the backend. */
export function createLessonInteractiveApplication(
  backend: LessonInteractiveBackend,
): LessonInteractiveApplication {
  const check = (problem: string | null) => {
    if (problem) throw new LessonInteractiveError(problem);
  };
  return {
    list: (lessonId) => backend.list(lessonId),
    get: (ref) => backend.get(ref),
    create: async (request) => {
      check(briefProblem(request.brief));
      return backend.create({ ...request, brief: request.brief.trim() });
    },
    requestChange: async (request) => {
      check(changeProblem(request.instruction));
      return backend.requestChange({
        ...request,
        instruction: request.instruction.trim(),
      });
    },
    retryBuild: (ref) => backend.retryBuild(ref),
    cancelBuild: (ref) => backend.cancelBuild(ref),
    saveDetails: async (request) => {
      check(detailsProblem(request.details));
      return backend.saveDetails({
        ...request,
        details: tidyDetails(request.details),
      });
    },
    restoreVersion: (request) => backend.restoreVersion(request),
    setPublishedVersion: (request) => backend.setPublishedVersion(request),
    reorder: (lessonId, orderedIds) => backend.reorder(lessonId, orderedIds),
    remove: (ref) => backend.remove(ref),
  };
}

export interface LearnerInteractiveApplication {
  list(lessonId: string): Promise<readonly LearnerInteractive[]>;
}
