import type { LessonFlow } from "./lesson-flow";
import type { AnimationBackend } from "./animation-backend";
import type { AnimatorModel } from "./animator-model";
import type { StyleInput } from "./style";
import type {
  CourseSpendResponse,
  LessonResponse,
  LessonPlanResponse,
} from "./dto";
import type { GenerationMode } from "./generation-mode";

export type StandaloneLessonResponse = Readonly<{
  activeOperation?: string;
  thumbnailOperation?: string;
  operationError?: string;
  spend?: CourseSpendResponse | null;
  id: string;
  ownerId: string;
  flow: LessonFlow;
  description: string;
  revision: number;
  approved: boolean;
  playbackContent?: LessonResponse | null;
  content: LessonResponse &
    Readonly<{
      storyboard: Readonly<{
        scenes: readonly Readonly<{ narrationText: string }>[];
      }> | null;
      alignment: Readonly<{ durationSec: number }> | null;
      animation: Readonly<{
        reviewStatus?: string;
        prepareElements?: boolean;
        backend?: "codex" | "direct";
        status: string;
        projectKey: string;
        outputHash?: string;
      }> | null;
    }>;
  turns: readonly Readonly<{ user: string; assistant: string }>[];
}>;
export type CreateLessonRequest = Readonly<{
  flow?: LessonFlow;
  title?: string;
  description?: string;
  minutes: number;
  style?: StyleInput;
  generationMode?: GenerationMode;
}>;
export type UpdateLessonRequest = CreateLessonRequest &
  Readonly<{ id: string; expectedRevision: number }>;
export type RegenerationStep = "script" | "speech" | "animation";
export type ReviseLessonRequest = Readonly<{
  sessionId?: string;
  scriptSessionId?: string;
  reviewerSessionId?: string;
  jobId?: string;
  id: string;
  expectedRevision: number;
  message?: string;
  regenerateFrom?: RegenerationStep;
  animatorModel?: AnimatorModel;
  prepareElements?: boolean;
  animationBackend?: AnimationBackend;
  generationMode?: GenerationMode;
}>;
export type LessonStage =
  | "automatic"
  | "approve"
  | "script/generate"
  | "storyboard"
  | "speech"
  | "animation"
  | "video";
export type SaveOutlineRequest = Readonly<{
  id: string;
  expectedRevision: number;
  outline: Omit<LessonPlanResponse, "lessonId" | "sources">;
}>;
export type SaveScriptRequest = Readonly<{
  id: string;
  expectedRevision: number;
  narrations: readonly string[];
}>;
export type CopyLessonRequest = Readonly<{
  id: string;
  courseId?: string;
  title?: string;
}>;
export interface StandaloneLessonBackend {
  copy?(request: CopyLessonRequest): Promise<StandaloneLessonResponse>;
  saveScript?(request: SaveScriptRequest): Promise<StandaloneLessonResponse>;
  saveOutline(request: SaveOutlineRequest): Promise<StandaloneLessonResponse>;
  refreshSpend?(id: string): Promise<StandaloneLessonResponse>;
  list(): Promise<readonly StandaloneLessonResponse[]>;
  get(id: string): Promise<StandaloneLessonResponse>;
  create(request: CreateLessonRequest): Promise<StandaloneLessonResponse>;
  update?(request: UpdateLessonRequest): Promise<StandaloneLessonResponse>;
  plan(request: ReviseLessonRequest): Promise<StandaloneLessonResponse>;
  advance(
    request: ReviseLessonRequest & { stage: LessonStage },
  ): Promise<StandaloneLessonResponse>;
}
export class ListStandaloneLessons {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute() {
    return this.backend.list();
  }
}
export class GetStandaloneLesson {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(id: string) {
    return this.backend.get(id);
  }
}
export class CreateStandaloneLesson {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: CreateLessonRequest) {
    return this.backend.create(normalizeLessonDetails(request));
  }
}
export class PlanStandaloneLesson {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: ReviseLessonRequest) {
    return this.backend.plan(request);
  }
}
export class AdvanceStandaloneLesson {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: ReviseLessonRequest & { stage: LessonStage }) {
    return this.backend.advance(request);
  }
}
export class RefreshStandaloneSpend {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(id: string) {
    return this.backend.refreshSpend
      ? this.backend.refreshSpend(id)
      : this.backend.get(id);
  }
}

export interface LessonApplication {
  copy?: Pick<CopyLesson, "execute">;
  saveScript?: Pick<SaveStandaloneScript, "execute">;
  prepareScript?: Pick<PrepareStandaloneScript, "execute">;
  saveOutline?: Pick<SaveStandaloneOutline, "execute">;
  refreshSpend?: Pick<RefreshStandaloneSpend, "execute">;
  list: Pick<ListStandaloneLessons, "execute">;
  get: Pick<GetStandaloneLesson, "execute">;
  create: Pick<CreateStandaloneLesson, "execute">;
  update?: Pick<UpdateStandaloneLesson, "execute">;
  plan: Pick<PlanStandaloneLesson, "execute">;
  advance: Pick<AdvanceStandaloneLesson, "execute">;
}

export class SaveStandaloneScript {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: SaveScriptRequest) {
    if (!this.backend.saveScript)
      throw new Error("Script editing is unavailable.");
    return this.backend.saveScript(request);
  }
}

export class PrepareStandaloneScript {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: ReviseLessonRequest) {
    return this.backend.advance({ ...request, stage: "script/generate" });
  }
}

export class SaveStandaloneOutline {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: SaveOutlineRequest) {
    return this.backend.saveOutline(request);
  }
}

export class UpdateStandaloneLesson {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: UpdateLessonRequest) {
    if (!this.backend.update) throw new Error("Draft updates are unavailable.");
    return this.backend.update(normalizeLessonDetails(request));
  }
}

export class CopyLesson {
  constructor(private readonly backend: StandaloneLessonBackend) {}
  execute(request: CopyLessonRequest) {
    if (!this.backend.copy) throw new Error("Lesson copying is unavailable.");
    return this.backend.copy(request);
  }
}

export const MAX_LESSON_MINUTES = 10;

export function normalizeLessonDetails<T extends CreateLessonRequest>(
  request: T,
) {
  let title = request.title?.trim() ?? "";
  let description = request.description?.trim() ?? "";
  if (
    (!title && !description) ||
    title.length > 120 ||
    description.length > 2000 ||
    !Number.isInteger(request.minutes) ||
    request.minutes < 1 ||
    request.minutes > MAX_LESSON_MINUTES
  )
    throw new Error(
      "Add a lesson title or describe what you want to learn, and choose a duration between 1 and 10 minutes.",
    );
  title ||= description.split(/\r?\n/)[0].slice(0, 120).trim();
  description ||= title;
  return { ...request, title, description };
}
