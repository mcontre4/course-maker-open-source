import type { AnimationBackend } from "./animation-backend";
import type { AnimatorModel } from "./animator-model";
import type { CourseResponse } from "./dto";
import type { GenerationMode } from "./generation-mode";

export type CourseMediaRequest = Readonly<{
  courseId: string;
  lessonId: string;
  stage: "storyboard" | "speech" | "animation" | "video";
  generationMode: GenerationMode;
  animatorModel?: AnimatorModel;
  prepareElements?: boolean;
  animationBackend?: AnimationBackend;
}>;
export interface CourseMediaBackend {
  advance(request: CourseMediaRequest): Promise<CourseResponse>;
}
export class AdvanceCourseMedia {
  constructor(private readonly backend: CourseMediaBackend) {}
  execute(request: CourseMediaRequest) {
    return this.backend.advance(request);
  }
}
