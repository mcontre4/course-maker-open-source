import { z } from "zod";
import type {
  LessonPlayback,
  LessonPlaybackRequest,
  LessonPlaybackResponse,
} from "../../application/lesson-playback";
import type { HttpTransport } from "./course-backend";

const selection = z.object({
  sourceHash: z.string().regex(/^[0-9a-f]{64}$/),
  videoReady: z.boolean(),
});
export class HttpLessonPlayback implements LessonPlayback {
  constructor(private readonly transport: HttpTransport) {}
  async select(
    request: LessonPlaybackRequest,
  ): Promise<LessonPlaybackResponse> {
    const base = request.courseId
      ? `/api/v1/courses/${encodeURIComponent(request.courseId)}/lessons/${encodeURIComponent(request.lessonId)}`
      : `/api/v1/lessons/${encodeURIComponent(request.lessonId)}`;
    const version = request.sourceHash
      ? `?v=${encodeURIComponent(request.sourceHash)}`
      : "";
    const response = await this.transport(`${base}/playback${version}`, {
      credentials: "same-origin",
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok)
      throw new Error("Playback could not be checked. Please retry.");
    const result = selection.parse(await response.json());
    return {
      ...result,
      previewUrl: `${base}/preview?v=${result.sourceHash}`,
      videoUrl: `${base}/video?v=${result.sourceHash}`,
    };
  }
}
