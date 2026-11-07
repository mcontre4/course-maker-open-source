import type {
  CourseMediaBackend,
  CourseMediaRequest,
} from "../../application/media";
import { HttpCourseBackend, type HttpTransport } from "./course-backend";

export class HttpCourseMedia implements CourseMediaBackend {
  constructor(
    private readonly transport: HttpTransport,
    private readonly courses: HttpCourseBackend,
  ) {}
  async advance(request: CourseMediaRequest) {
    const route = {
      video: "video",
      storyboard: "storyboards",
      speech: "speech",
      animation: "animations",
    }[request.stage];
    const response = await this.transport(
      `/api/v1/courses/${encodeURIComponent(request.courseId)}/${route}/generate`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lessonId: request.lessonId,
          ...(request.stage === "speech"
            ? {}
            : { generationMode: request.generationMode }),
          ...(["animation", "video"].includes(request.stage) &&
          request.animationBackend
            ? { animationBackend: request.animationBackend }
            : {}),
          ...(["animation", "video"].includes(request.stage) &&
          request.prepareElements !== undefined
            ? { prepareElements: request.prepareElements }
            : {}),
          ...(["animation", "video"].includes(request.stage) &&
          request.animatorModel
            ? { animatorModel: request.animatorModel }
            : {}),
          ...(request.stage === "animation"
            ? { visualStyle: "Follow the saved course and lesson style." }
            : {}),
        }),
        signal: AbortSignal.timeout(1200000),
      },
    );
    if (!response.ok) {
      const value: unknown = await response.json().catch(() => null);
      throw new Error(
        value &&
          typeof value === "object" &&
          "detail" in value &&
          typeof value.detail === "string"
          ? value.detail
          : "Lesson generation failed. Completed stages are saved; reload and continue.",
      );
    }
    return this.courses.get(request.courseId);
  }
}
