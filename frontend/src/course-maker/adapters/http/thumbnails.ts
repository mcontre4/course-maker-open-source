import type {
  ThumbnailBackend,
  ThumbnailRequest,
} from "../../application/thumbnails";
import type { CourseBackend } from "../../application/backend";
import type { StandaloneLessonBackend } from "../../application/standalone-lessons";
import type { HttpTransport } from "./course-backend";

export class HttpThumbnails implements ThumbnailBackend {
  constructor(
    private readonly transport: HttpTransport,
    private readonly courses: CourseBackend,
    private readonly lessons: StandaloneLessonBackend,
  ) {}
  async generate(request: ThumbnailRequest) {
    const id = encodeURIComponent(request.id);
    const suffix = request.lessonId
      ? `/lessons/${encodeURIComponent(request.lessonId)}`
      : "";
    const response = await this.transport(
      `/api/v1/${request.kind === "course" ? "courses" : "lessons"}/${id}${suffix}/thumbnail`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ regenerate: request.regenerate ?? false }),
        signal: AbortSignal.timeout(120000),
      },
    );
    if (!response.ok) {
      const data: unknown = await response.json().catch(() => null);
      throw new Error(
        data &&
          typeof data === "object" &&
          "detail" in data &&
          typeof data.detail === "string"
          ? data.detail
          : "Thumbnail could not be generated. Your saved content is unchanged.",
      );
    }
    return request.kind === "course"
      ? this.courses.get(request.id)
      : this.lessons.get(request.id);
  }
}
