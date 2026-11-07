import { z } from "zod";
import type { HttpTransport } from "./course-backend";
import type {
  InteractiveRef,
  LessonInteractiveBackend,
  LearnerInteractiveApplication,
} from "../../application/lesson-interactives";
import { interactiveBuildStages } from "../../application/lesson-interactives";

const learnerInteractive = z.object({
  id: z.string(),
  lessonId: z.string(),
  version: z.number().int().positive(),
  title: z.string(),
  goal: z.string(),
  prompts: z.array(z.string()),
  html: z.string(),
});
const interactive = z.object({
  id: z.string(),
  lessonId: z.string(),
  brief: z.string(),
  title: z.string(),
  goal: z.string(),
  prompts: z.array(z.string()),
  revision: z.number().int().positive(),
  createdAt: z.string(),
  updatedAt: z.string(),
  versions: z.array(
    z.object({
      number: z.number().int().positive(),
      request: z.string(),
      createdAt: z.string(),
    }),
  ),
  currentVersion: z.number().int().positive().nullable(),
  html: z.string().nullable(),
  publishedVersion: z.number().int().positive().nullable(),
  publishedHtml: z.string().nullable(),
  build: z
    .object({
      request: z.string(),
      startedAt: z.string(),
      stage: z.enum(interactiveBuildStages),
    })
    .nullable(),
  failure: z.object({ request: z.string(), message: z.string() }).nullable(),
});
const collection = z.object({ items: z.array(interactive) });

class InteractiveTransport {
  constructor(private readonly transport: HttpTransport) {}

  async request(
    path: string,
    method = "GET",
    body?: unknown,
  ): Promise<unknown> {
    const response = await this.transport(path, {
      method,
      credentials: "same-origin",
      signal: AbortSignal.timeout(30000),
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.ok && response.status === 204) return undefined;
    const data: unknown = await response.json();
    if (!response.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? data.detail
          : null;
      throw new Error(
        typeof detail === "string"
          ? detail
          : "The interactive request failed. Please try again.",
      );
    }
    return data;
  }
}

export class HttpLessonInteractives implements LessonInteractiveBackend {
  private readonly http: InteractiveTransport;
  constructor(transport: HttpTransport) {
    this.http = new InteractiveTransport(transport);
  }
  private path(lessonId: string, id?: string) {
    const root = `/api/v1/lessons/${encodeURIComponent(lessonId)}/interactives`;
    return id === undefined ? root : root + "/" + encodeURIComponent(id);
  }
  async list(lessonId: string) {
    return collection.parse(await this.http.request(this.path(lessonId))).items;
  }
  async get(ref: InteractiveRef) {
    return interactive.parse(
      await this.http.request(this.path(ref.lessonId, ref.id)),
    );
  }
  async create(request: Parameters<LessonInteractiveBackend["create"]>[0]) {
    return interactive.parse(
      await this.http.request(this.path(request.lessonId), "POST", {
        brief: request.brief,
        generationMode: request.generationMode,
      }),
    );
  }
  async requestChange(
    request: Parameters<LessonInteractiveBackend["requestChange"]>[0],
  ) {
    return interactive.parse(
      await this.http.request(
        this.path(request.lessonId, request.id) + "/changes",
        "POST",
        {
          instruction: request.instruction,
          expectedRevision: request.expectedRevision,
        },
      ),
    );
  }
  async retryBuild(ref: InteractiveRef) {
    return interactive.parse(
      await this.http.request(
        this.path(ref.lessonId, ref.id) + "/build/retry",
        "POST",
      ),
    );
  }
  async cancelBuild(ref: InteractiveRef) {
    return interactive.parse(
      await this.http.request(
        this.path(ref.lessonId, ref.id) + "/build/cancel",
        "POST",
      ),
    );
  }
  async saveDetails(
    request: Parameters<LessonInteractiveBackend["saveDetails"]>[0],
  ) {
    return interactive.parse(
      await this.http.request(
        this.path(request.lessonId, request.id),
        "PATCH",
        { ...request.details, expectedRevision: request.expectedRevision },
      ),
    );
  }
  async restoreVersion(
    request: Parameters<LessonInteractiveBackend["restoreVersion"]>[0],
  ) {
    return interactive.parse(
      await this.http.request(
        this.path(request.lessonId, request.id) +
          `/versions/${request.version}/restore`,
        "POST",
        { expectedRevision: request.expectedRevision },
      ),
    );
  }
  async setPublishedVersion(
    request: Parameters<LessonInteractiveBackend["setPublishedVersion"]>[0],
  ) {
    return interactive.parse(
      await this.http.request(
        this.path(request.lessonId, request.id) + "/published",
        "PUT",
        { version: request.version },
      ),
    );
  }
  async reorder(lessonId: string, orderedIds: readonly string[]) {
    return collection.parse(
      await this.http.request(this.path(lessonId) + "/order", "PUT", {
        ids: orderedIds,
      }),
    ).items;
  }
  async remove(ref: InteractiveRef) {
    await this.http.request(this.path(ref.lessonId, ref.id), "DELETE");
  }
}

export class HttpLearnerInteractives implements LearnerInteractiveApplication {
  private readonly http: InteractiveTransport;
  constructor(transport: HttpTransport) {
    this.http = new InteractiveTransport(transport);
  }
  async list(lessonId: string) {
    return z
      .object({ items: z.array(learnerInteractive) })
      .parse(
        await this.http.request(
          `/api/v1/published/lessons/${encodeURIComponent(lessonId)}/interactives`,
        ),
      ).items;
  }
}
