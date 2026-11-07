import type { CourseResponse } from "./dto";
import type { StandaloneLessonResponse } from "./standalone-lessons";

export type ThumbnailRequest = Readonly<{
  kind: "course" | "lesson";
  id: string;
  lessonId?: string;
  regenerate?: boolean;
}>;

export interface ThumbnailBackend {
  generate(
    request: ThumbnailRequest,
  ): Promise<CourseResponse | StandaloneLessonResponse>;
}

export class GenerateThumbnail {
  constructor(private readonly backend: ThumbnailBackend) {}
  execute(request: ThumbnailRequest) {
    return this.backend.generate(request);
  }
}
