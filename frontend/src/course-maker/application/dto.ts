import type { StyleInput, StyleResponse } from "./style";
import type { GenerationMode } from "./generation-mode";
import type { Course } from "../domain/course";

// Application-owned read models. Correct quiz answers stay behind the use case.
export type DurationInput =
  | Readonly<{ mode: "total"; hours: number }>
  | Readonly<{ mode: "weekly"; weeks: number; hoursPerWeek: number }>;
export type CreateCourseRequest = Readonly<{
  title: string;
  description: string;
  duration: DurationInput;
  style?: StyleInput;
  generationMode?: GenerationMode;
}>;
export type LessonPlanResponse = Readonly<{
  lessonId: string;
  objectives: readonly string[];
  assumedKnowledge: readonly string[];
  introducedKnowledge: readonly string[];
  requiredFacts: readonly string[];
  equations: readonly string[];
  misconceptions: readonly string[];
  scopeBoundaries: readonly string[];
  beats: readonly Readonly<{
    title: string;
    purpose: string;
    teachingNotes: string;
    concepts: readonly string[];
    seconds: number;
    checkQuestion: string;
    expectedAnswer: string;
  }>[];
  examples: readonly Readonly<{
    problem: string;
    steps: readonly string[];
    result: string;
  }>[];
  sources: readonly Readonly<{ title: string; url: string }>[];
  feasibilityStatus?: "feasible" | "infeasible" | null;
  feasibilityExplanation?: string;
  recommendedVideoMinutes?: number | null;
  recommendedScopeAdjustment?: string;
}>;
export type InteractiveResponse = Readonly<{
  planHash: string;
  reason: string;
  spec: Readonly<{
    kind: "pendulum" | "custom";
    title: string;
    objective: string;
    explanation: string;
    controls: readonly string[];
    behavior: string;
    prompts: readonly string[];
    acceptanceCriteria: readonly string[];
    initialLength: number;
    initialGravity: number;
    initialAngle: number;
  }> | null;
  html: string | null;
}>;
export type LessonResponse = Readonly<{
  agentSessions?: Readonly<Record<string, string | null>> | null;
  style?: StyleResponse | null;
  styleHistory?: readonly StyleResponse[];
  storyboard?: Readonly<{
    scenes: readonly Readonly<{ narrationText: string }>[];
  }> | null;
  alignment?: Readonly<{ durationSec: number }> | null;
  animation?: Readonly<{
    reviewStatus?: string;
    prepareElements?: boolean;
    backend?: "codex" | "direct";
    status: string;
    projectKey: string;
    outputHash?: string;
  }> | null;
  id: string;
  title: string;
  image: string;
  topics: readonly string[];
  minutes: number;
  videoUrl: string | null;
  interactive?: InteractiveResponse | null;
  plan?: LessonPlanResponse | null;
  quiz: readonly Readonly<{
    id: string;
    prompt: string;
    options: readonly string[];
  }>[];
}>;
export type ChapterResponse = Readonly<{
  id: string;
  title: string;
  summary: string;
  image: string;
  lessons: readonly LessonResponse[];
}>;
export type CourseResponse = Readonly<{
  ownerId?: string | null;
  activeOperation?: string;
  thumbnailOperation?: string;
  operationError?: string;
  styleHistory?: readonly StyleResponse[];
  style?: StyleResponse | null;
  spend?: CourseSpendResponse | null;
  id: string;
  title: string;
  description: string;
  duration: DurationInput;
  image: string;
  status: "draft" | "ready";
  chapters: readonly ChapterResponse[];
  reviewed: readonly string[];
  completed: readonly string[];
  messages: readonly Readonly<{ role: "guide" | "learner"; text: string }>[];
  syllabus?: SyllabusSessionResponse;
}>;
export type SpendTotalResponse = Readonly<{
  credits?: string;
  knownUsd: string;
  pendingCalls: number;
  estimatedCalls: number;
  calls: number;
  inputTokens: number;
  outputTokens: number;
}>;
export type CourseSpendResponse = Readonly<{
  steps?: readonly Readonly<{
    id: string;
    lessonId: string | null;
    stage: string;
    startedAt: number;
    finishedAt: number | null;
    backend?: string | null;
  }>[];
  currency: "USD";
  total: SpendTotalResponse;
  shared: SpendTotalResponse;
  lessons: readonly Readonly<{ lessonId: string; total: SpendTotalResponse }>[];
  breakdown: readonly Readonly<{
    lessonId: string | null;
    stage: string;
    provider: string;
    model: string;
    total: SpendTotalResponse;
  }>[];
}>;
export type SyllabusSessionResponse = Readonly<{
  sessionId?: string;
  revision: number;
  outcomes: readonly string[];
  warnings: readonly string[];
  lessons: readonly Readonly<{
    id: string;
    week: number;
    objectives: readonly string[];
    videoMinutes: number;
    practiceMinutes: number;
    readingMinutes: number;
    reviewMinutes: number;
  }>[];
}>;
export type GenerateSyllabusRequest = Readonly<{
  sessionId?: string;
  courseId: string;
  message: string;
  expectedRevision: number;
  generationMode?: GenerationMode;
}>;
export type QuizResultResponse = Readonly<{
  score: number;
  total: number;
  passed: boolean;
  feedback: readonly Readonly<{ correct: boolean; explanation: string }>[];
}>;
export type EditTopicRequest = Readonly<{
  courseId: string;
  lessonId: string;
  topic: string;
  operation: "add" | "remove";
}>;

export function toResponse(course: Course): CourseResponse {
  return {
    id: course.id,
    title: course.title,
    description: course.description,
    duration: { ...course.duration },
    image: course.image,
    status: course.status,
    reviewed: [...course.reviewed],
    completed: [...course.completed],
    messages: course.messages.map((m) => ({ ...m })),
    chapters: course.chapters.map((c) => ({
      id: c.id,
      title: c.title,
      summary: c.summary,
      image: c.image,
      lessons: c.lessons.map((l) => ({
        id: l.id,
        title: l.title,
        image: l.image,
        topics: [...l.topics],
        minutes: l.minutes,
        videoUrl: l.videoUrl,
        quiz: l.quiz.map((q) => ({
          id: q.id,
          prompt: q.prompt,
          options: [...q.options],
        })),
      })),
    })),
  };
}
