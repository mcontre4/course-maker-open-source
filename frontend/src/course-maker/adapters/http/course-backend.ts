import { interactiveSchema } from "./interactive-schema";
import { z } from "zod";
import { styleSchema } from "./style-schema";
import type { GenerateLessonRequest } from "../../application/generation-mode";
import type { CourseBackend } from "../../application/backend";
import type {
  CourseResponse,
  CreateCourseRequest,
  EditTopicRequest,
  GenerateSyllabusRequest,
} from "../../application/dto";

export type HttpTransport = (
  url: string,
  init?: RequestInit,
) => Promise<Response>;
const question = z.object({
  id: z.string(),
  prompt: z.string(),
  options: z.array(z.string()),
});
const spendTotal = z.object({
  credits: z
    .string()
    .regex(/^\d+(\.\d+)?$/)
    .optional(),
  knownUsd: z.string().regex(/^\d+(\.\d+)?$/),
  pendingCalls: z.number().int().nonnegative(),
  estimatedCalls: z.number().int().nonnegative(),
  calls: z.number().int().nonnegative(),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
});
export const spend = z.object({
  steps: z
    .array(
      z.object({
        id: z.string(),
        lessonId: z.string().nullable(),
        stage: z.string(),
        startedAt: z.number().nonnegative(),
        finishedAt: z.number().nonnegative().nullable(),
        backend: z.string().nullable().optional(),
      }),
    )
    .optional(),
  currency: z.literal("USD"),
  total: spendTotal,
  shared: spendTotal,
  lessons: z.array(z.object({ lessonId: z.string(), total: spendTotal })),
  breakdown: z.array(
    z.object({
      lessonId: z.string().nullable(),
      stage: z.string(),
      provider: z.string(),
      model: z.string(),
      total: spendTotal,
    }),
  ),
});
export const lessonPlan = z.object({
  lessonId: z.string(),
  objectives: z.array(z.string()),
  assumedKnowledge: z.array(z.string()),
  introducedKnowledge: z.array(z.string()),
  requiredFacts: z.array(z.string()),
  equations: z.array(z.string()),
  misconceptions: z.array(z.string()),
  scopeBoundaries: z.array(z.string()),
  beats: z.array(
    z.object({
      title: z.string(),
      purpose: z.string(),
      teachingNotes: z.string(),
      concepts: z.array(z.string()),
      seconds: z.number(),
      checkQuestion: z.string(),
      expectedAnswer: z.string(),
    }),
  ),
  examples: z.array(
    z.object({
      problem: z.string(),
      steps: z.array(z.string()),
      result: z.string(),
    }),
  ),
  sources: z.array(z.object({ title: z.string(), url: z.string().url() })),
  feasibilityStatus: z.enum(["feasible", "infeasible"]).nullable().optional(),
  feasibilityExplanation: z.string().optional(),
  recommendedVideoMinutes: z.number().int().nullable().optional(),
  recommendedScopeAdjustment: z.string().optional(),
});
const style = z.preprocess(
  (value) =>
    value && typeof value === "object"
      ? Object.fromEntries(
          Object.entries(value).map(([key, item]) => [
            key.replace(/_([a-z])/g, (_, letter: string) =>
              letter.toUpperCase(),
            ),
            item,
          ]),
        )
      : value,
  styleSchema,
);
const lesson = z.object({
  agentSessions: z
    .record(z.string(), z.string().nullable())
    .nullable()
    .optional(),
  storyboard: z
    .object({ scenes: z.array(z.object({ narrationText: z.string() })) })
    .nullable()
    .optional(),
  alignment: z.object({ durationSec: z.number() }).nullable().optional(),
  animation: z
    .object({
      status: z.string(),
      reviewStatus: z.string().optional(),
      prepareElements: z.boolean().optional(),
      backend: z.enum(["codex", "direct"]).optional(),
      projectKey: z.string(),
      outputHash: z.string().optional(),
    })
    .nullable()
    .optional(),
  style: style.nullable().optional(),
  styleHistory: z.array(style).optional(),
  id: z.string(),
  title: z.string(),
  image: z.string(),
  topics: z.array(z.string()),
  minutes: z.number(),
  videoUrl: z.string().nullable(),
  interactive: interactiveSchema.nullable().optional(),
  plan: lessonPlan.nullable().optional(),
  quiz: z.array(question),
});
const duration = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("total"), hours: z.number() }),
  z.object({
    mode: z.literal("weekly"),
    weeks: z.number(),
    hoursPerWeek: z.number(),
  }),
]);
const course = z.object({
  ownerId: z.string().nullable().optional(),
  activeOperation: z.string().optional(),
  thumbnailOperation: z.string().optional(),
  operationError: z.string().optional(),
  styleHistory: z.array(style).optional(),
  style: style.nullable().optional(),
  id: z.string(),
  title: z.string(),
  description: z.string(),
  duration,
  image: z.string(),
  status: z.enum(["draft", "ready"]),
  chapters: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      summary: z.string(),
      image: z.string(),
      lessons: z.array(lesson),
    }),
  ),
  reviewed: z.array(z.string()),
  completed: z.array(z.string()),
});
const plannedLesson = z.object({
  lesson_id: z.string(),
  week: z.number(),
  objectives: z.array(z.string()),
  video_minutes: z.number(),
  practice_minutes: z.number(),
  reading_minutes: z.number(),
  review_minutes: z.number(),
});
const session = z.object({
  sessionId: z.string().optional(),
  revision: z.number().int().nonnegative(),
  turns: z.array(z.object({ user: z.string(), assistant: z.string() })),
  curriculum: z
    .object({
      outcomes: z.array(z.string()),
      warnings: z.array(z.string()),
      chapters: z.array(z.object({ lessons: z.array(plannedLesson) })),
    })
    .nullable(),
});
type ApiCourse = z.infer<typeof course>;
type ApiSession = z.infer<typeof session>;

function readModel(
  value: ApiCourse,
  conversation?: ApiSession,
): CourseResponse {
  const plan = conversation?.curriculum;
  return {
    ...value,
    messages:
      conversation?.turns.flatMap((turn) => [
        { role: "learner" as const, text: turn.user },
        { role: "guide" as const, text: turn.assistant },
      ]) ?? [],
    syllabus: conversation
      ? {
          revision: conversation.revision,
          sessionId: conversation.sessionId?.startsWith("agent_")
            ? conversation.sessionId
            : undefined,
          outcomes: plan?.outcomes ?? [],
          warnings: plan?.warnings ?? [],
          lessons:
            plan?.chapters.flatMap((ch) =>
              ch.lessons.map((ls) => ({
                id: ls.lesson_id,
                week: ls.week,
                objectives: ls.objectives,
                videoMinutes: ls.video_minutes,
                practiceMinutes: ls.practice_minutes,
                readingMinutes: ls.reading_minutes,
                reviewMinutes: ls.review_minutes,
              })),
            ) ?? [],
        }
      : undefined,
  };
}

export class HttpCourseBackend implements CourseBackend {
  constructor(
    private readonly transport: HttpTransport,
    private readonly base = "/api/v1",
  ) {}

  private async request(
    path: string,
    method = "GET",
    body?: unknown,
  ): Promise<unknown> {
    let response: Response;
    try {
      response = await this.transport(this.base + path, {
        method,
        credentials: "same-origin",
        headers:
          body === undefined
            ? undefined
            : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(240000),
      });
    } catch {
      throw new Error(
        "Couldn’t reach the course server. Your draft is saved if it was already created. Check the connection and reload before retrying.",
      );
    }
    if (!response.ok) {
      if (response.status === 409)
        throw Object.assign(
          new Error(
            "This course changed in another request. The latest version will be loaded; review it before sending again.",
          ),
          { kind: "conflict" },
        );
      if (response.status === 401 || response.status === 403)
        throw new Error(
          "The course server could not authorize this request. Check the server connection settings.",
        );
      if (response.status === 503)
        throw new Error(
          "Your course guide is unavailable right now. Your saved course is unchanged. Try again shortly.",
        );
      const error = (await response.json().catch(() => null)) as {
        detail?: unknown;
      } | null;
      throw new Error(
        typeof error?.detail === "string"
          ? error.detail
          : "The course request could not be completed.",
      );
    }
    try {
      const data: unknown = await response.json();
      return {
        ...(data as object),
        activeOperation: response.headers.get("X-Active-Operation") ?? "",
        thumbnailOperation: response.headers.get("X-Thumbnail-Operation") ?? "",
        operationError: response.headers.get("X-Operation-Error") ?? "",
      };
    } catch {
      throw new Error(
        "The course server returned an unreadable response. Reload to check your saved course before retrying.",
      );
    }
  }
  private async read<T>(
    schema: z.ZodType<T>,
    path: string,
    method = "GET",
    body?: unknown,
  ): Promise<T> {
    const parsed = schema.safeParse(await this.request(path, method, body));
    if (!parsed.success)
      throw new Error(
        "The course server returned an unexpected response. Reload to check your saved course before retrying.",
      );
    return parsed.data;
  }
  async list() {
    const values: CourseResponse[] = [];
    let offset = 0,
      total = 1;
    while (offset < total) {
      const page = await this.read(
        z.object({
          items: z.array(course),
          total: z.number().int().nonnegative(),
        }),
        `/courses?limit=100&offset=${offset}`,
      );
      values.push(...page.items.map((item) => readModel(item)));
      total = page.total;
      if (!page.items.length) break;
      offset += page.items.length;
    }
    return values;
  }
  async get(id: string) {
    const path = `/courses/${encodeURIComponent(id)}`;
    const [value, conversation] = await Promise.all([
      this.read(course, path),
      this.read(session, path + "/syllabus/session"),
    ]);
    return readModel(value, conversation);
  }
  async refreshSpend(id: string) {
    await this.read(
      spend,
      `/courses/${encodeURIComponent(id)}/spend/refresh`,
      "POST",
    );
    return this.get(id);
  }
  async update(id: string, request: CreateCourseRequest) {
    return readModel(
      await this.read(
        course,
        `/courses/${encodeURIComponent(id)}`,
        "PUT",
        request,
      ),
    );
  }
  async create(request: CreateCourseRequest) {
    return readModel(await this.read(course, "/courses", "POST", request));
  }
  async generate(request: GenerateSyllabusRequest) {
    const value = await this.read(
      z.object({ course, session }),
      `/courses/${encodeURIComponent(request.courseId)}/syllabus/generate`,
      "POST",
      {
        message: request.message,
        expectedRevision: request.expectedRevision,
        sessionId: request.sessionId,
        generationMode: request.generationMode,
      },
    );
    return readModel(value.course, value.session);
  }
  async generateLesson(request: GenerateLessonRequest) {
    return readModel(
      await this.read(
        course,
        `/courses/${encodeURIComponent(request.courseId)}/lessons/generate`,
        "POST",
        { lessonId: request.lessonId, generationMode: request.generationMode },
      ),
    );
  }
  async edit(request: EditTopicRequest) {
    await this.request(
      `/courses/${encodeURIComponent(request.courseId)}/lessons/${encodeURIComponent(request.lessonId)}/topics`,
      "PATCH",
      { topic: request.topic, operation: request.operation },
    );
    return this.get(request.courseId);
  }
  async approve(id: string) {
    await this.request(
      `/courses/${encodeURIComponent(id)}/syllabus/approve`,
      "POST",
    );
    return this.get(id);
  }
  async review(request: Readonly<{ courseId: string; lessonId: string }>) {
    await this.request(
      `/courses/${encodeURIComponent(request.courseId)}/lessons/${encodeURIComponent(request.lessonId)}/review`,
      "POST",
    );
    return this.get(request.courseId);
  }
  async submit(
    request: Readonly<{
      courseId: string;
      lessonId: string;
      answers: readonly number[];
    }>,
  ) {
    return this.read(
      z.object({
        score: z.number(),
        total: z.number(),
        passed: z.boolean(),
        feedback: z.array(
          z.object({ correct: z.boolean(), explanation: z.string() }),
        ),
      }),
      `/courses/${encodeURIComponent(request.courseId)}/lessons/${encodeURIComponent(request.lessonId)}/quiz/attempts`,
      "POST",
      { answers: request.answers },
    );
  }
}
