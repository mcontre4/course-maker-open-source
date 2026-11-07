import { z } from "zod";
import type {
  InternalTools,
  LessonReference,
} from "../../application/internal-tools";
import { spend, type HttpTransport } from "./course-backend";

const diagnostics = z.object({
  lessonId: z.string(),
  courseId: z.string().nullable(),
  title: z.string(),
  spend,
  generationSeconds: z.number().nonnegative().nullable(),
  generationActive: z.boolean(),
});

export class HttpInternalTools implements InternalTools {
  constructor(private readonly transport: HttpTransport) {}

  async inspect(reference: LessonReference, key: string, refresh = false) {
    const query = reference.courseId
      ? "?course_id=" + encodeURIComponent(reference.courseId)
      : "";
    const response = await this.transport(
      `/api/v1/internal/lessons/${encodeURIComponent(reference.lessonId)}${refresh ? "/refresh" : ""}${query}`,
      {
        method: refresh ? "POST" : "GET",
        headers: { "X-Internal-Tools-Key": key },
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(120000),
      },
    );
    if (!response.ok) {
      if (response.status === 403)
        throw new Error("Internal access key is invalid.");
      if (response.status === 404)
        throw new Error("Lesson not found, or internal tools are disabled.");
      throw new Error("Couldn’t load lesson diagnostics. Try again.");
    }
    return diagnostics.parse(await response.json());
  }
}
