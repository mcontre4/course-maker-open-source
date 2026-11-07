import { interactiveSchema } from "./interactive-schema";
import { z } from "zod";
import { styleSchema } from "./style-schema";
import type {
  CopyLessonRequest,
  CreateLessonRequest,
  SaveOutlineRequest,
  SaveScriptRequest,
  UpdateLessonRequest,
  ReviseLessonRequest,
  LessonStage,
  StandaloneLessonBackend,
  StandaloneLessonResponse,
} from "../../application/standalone-lessons";
import { lessonPlan, spend, type HttpTransport } from "./course-backend";

const lessonContent = z.object({
  agentSessions: z
    .record(z.string(), z.string().nullable())
    .nullable()
    .optional(),
  style: styleSchema.nullable().optional(),
  styleHistory: z.array(styleSchema).optional(),
  id: z.string(),
  title: z.string(),
  image: z.string(),
  topics: z.array(z.string()),
  minutes: z.number().int().min(1).max(10),
  videoUrl: z.string().nullable(),
  interactive: interactiveSchema.nullable().optional(),
  quiz: z.array(
    z.object({
      id: z.string(),
      prompt: z.string(),
      options: z.array(z.string()),
    }),
  ),
  plan: lessonPlan.nullable(),
  storyboard: z
    .object({ scenes: z.array(z.object({ narrationText: z.string() })) })
    .nullable(),
  alignment: z.object({ durationSec: z.number() }).nullable(),
  animation: z
    .object({
      status: z.string(),
      reviewStatus: z.string().optional(),
      prepareElements: z.boolean().optional(),
      backend: z.enum(["codex", "direct"]).optional(),
      projectKey: z.string(),
      outputHash: z.string().optional(),
    })
    .nullable(),
});
const standalone = z.object({
  activeOperation: z.string().optional(),
  thumbnailOperation: z.string().optional(),
  operationError: z.string().optional(),
  id: z.string(),
  ownerId: z.string(),
  flow: z.enum(["guided", "automatic"]).default("guided"),
  description: z.string(),
  revision: z.number().int().nonnegative(),
  approved: z.boolean(),
  turns: z.array(z.object({ user: z.string(), assistant: z.string() })),
  content: lessonContent,
  playbackContent: lessonContent.nullable().optional(),
});
// Application DTOs embedded in the API use snake_case; transport views use camelCase.
function camelKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(camelKeys);
  if (value !== null && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()),
        camelKeys(item),
      ]),
    );
  return value;
}
export class HttpStandaloneLessons implements StandaloneLessonBackend {
  constructor(private readonly transport: HttpTransport) {}
  private async request(
    path = "",
    body?: unknown,
    method?: string,
  ): Promise<unknown> {
    let response: Response;
    try {
      response = await this.transport("/api/v1/lessons" + path, {
        method: method ?? (body === undefined ? "GET" : "POST"),
        credentials: "same-origin",
        headers:
          body === undefined
            ? undefined
            : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(1200000),
      });
    } catch {
      throw new Error(
        "Connection interrupted. Reload your saved lesson before trying again.",
      );
    }
    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? data.detail
          : null;
      throw Object.assign(
        new Error(
          typeof detail === "string"
            ? detail
            : "The lesson request could not be completed. Reload and try again.",
        ),
        { status: response.status },
      );
    }
    return {
      ...(camelKeys(data) as object),
      activeOperation: response.headers.get("X-Active-Operation") ?? "",
      thumbnailOperation: response.headers.get("X-Thumbnail-Operation") ?? "",
      operationError: response.headers.get("X-Operation-Error") ?? "",
    };
  }
  private read(value: unknown): StandaloneLessonResponse {
    const result = standalone.safeParse(value);
    if (!result.success)
      throw new Error(
        "Unexpected lesson response. Reload to check your saved lesson.",
      );
    return result.data;
  }
  async list() {
    const items: StandaloneLessonResponse[] = [];
    for (let offset = 0; ; offset += 100) {
      const page = z
        .object({ items: z.array(standalone) })
        .parse(await this.request(`?limit=100&offset=${offset}`));
      items.push(...page.items);
      if (page.items.length < 100) return items;
    }
  }
  async get(id: string) {
    return this.read(await this.request("/" + encodeURIComponent(id)));
  }
  async refreshSpend(id: string) {
    spend.parse(
      await this.request(`/${encodeURIComponent(id)}/spend/refresh`, {}),
    );
    return this.get(id);
  }
  async update(request: UpdateLessonRequest) {
    return this.read(
      await this.request(
        `/${encodeURIComponent(request.id)}`,
        {
          flow: request.flow,
          title: request.title,
          description: request.description,
          minutes: request.minutes,
          expectedRevision: request.expectedRevision,
          style: request.style,
        },
        "PUT",
      ),
    );
  }
  async create(request: CreateLessonRequest) {
    return this.read(await this.request("", request));
  }
  async copy({ id, courseId, title }: CopyLessonRequest) {
    return this.read(
      await this.request(`/${encodeURIComponent(id)}/copy`, {
        courseId,
        title,
      }),
    );
  }
  async saveOutline(request: SaveOutlineRequest) {
    const lesson = this.read(
      await this.request(
        `/${encodeURIComponent(request.id)}/outline`,
        {
          expectedRevision: request.expectedRevision,
          outline: request.outline,
        },
        "PUT",
      ),
    );
    return lesson;
  }
  async saveScript(request: SaveScriptRequest) {
    return this.read(
      await this.request(
        `/${encodeURIComponent(request.id)}/script`,
        {
          expectedRevision: request.expectedRevision,
          narrations: request.narrations,
        },
        "PUT",
      ),
    );
  }
  async plan(request: ReviseLessonRequest) {
    const lesson = this.read(
      await this.request(`/${encodeURIComponent(request.id)}/plan`, {
        expectedRevision: request.expectedRevision,
        message: request.message,
        sessionId: request.sessionId,
        jobId: request.jobId,
        generationMode: request.generationMode,
      }),
    );
    return lesson;
  }
  async advance(request: ReviseLessonRequest & { stage: LessonStage }) {
    const lesson = this.read(
      await this.request(
        `/${encodeURIComponent(request.id)}/${request.stage}`,
        {
          expectedRevision: request.expectedRevision,
          generationMode: request.generationMode,
          message: request.message,
          sessionId: request.sessionId,
          scriptSessionId: request.scriptSessionId,
          reviewerSessionId: request.reviewerSessionId,
          jobId: request.jobId,
          ...(request.regenerateFrom
            ? { regenerateFrom: request.regenerateFrom }
            : {}),
          ...(request.stage === "automatic"
            ? { message: request.message }
            : {}),
          ...(["animation", "video", "automatic"].includes(request.stage) &&
          request.animationBackend
            ? { animationBackend: request.animationBackend }
            : {}),
          ...(["animation", "video", "automatic"].includes(request.stage) &&
          request.prepareElements !== undefined
            ? { prepareElements: request.prepareElements }
            : {}),
          ...(["animation", "video", "automatic"].includes(request.stage) &&
          request.animatorModel
            ? { animatorModel: request.animatorModel }
            : {}),
        },
      ),
    );
    return lesson;
  }
}
