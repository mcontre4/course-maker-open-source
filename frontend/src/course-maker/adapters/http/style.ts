import { z } from "zod";
import type { StyleBackend, UpdateStyleRequest } from "../../application/style";
import type { HttpTransport } from "./course-backend";
import { HttpCourseBackend } from "./course-backend";
import { HttpStandaloneLessons } from "./standalone-lessons";

const voicesSchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      description: z.string(),
      previewUrl: z.string().url().nullable(),
      labels: z.array(z.string()),
    }),
  ),
});

export class HttpStyleBackend implements StyleBackend {
  constructor(
    private readonly transport: HttpTransport,
    private readonly courses: HttpCourseBackend,
    private readonly lessons: HttpStandaloneLessons,
  ) {}
  private async request(path: string, body?: unknown) {
    const response = await this.transport("/api/v1" + path, {
      method: body === undefined ? "GET" : "POST",
      credentials: "same-origin",
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(180000),
    });
    const value: unknown = await response.json();
    if (!response.ok) {
      const error = z.object({ detail: z.string() }).safeParse(value);
      throw new Error(
        error.success
          ? error.data.detail
          : "Could not update style. Reload and try again.",
      );
    }
    return value;
  }
  async voices() {
    const data = voicesSchema.parse(await this.request("/voices"));
    return data.items;
  }
  async update(request: UpdateStyleRequest) {
    const path =
      request.kind === "lesson"
        ? `/lessons/${encodeURIComponent(request.id)}/style`
        : `/courses/${encodeURIComponent(request.id)}${request.lessonId ? `/lessons/${encodeURIComponent(request.lessonId)}` : ""}/style`;
    await this.request(path, {
      style: request.style,
      expectedVersion: request.expectedVersion,
      generationMode: request.generationMode,
    });
    return request.kind === "lesson"
      ? this.lessons.get(request.id)
      : this.courses.get(request.id);
  }
}
