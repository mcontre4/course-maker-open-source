export type GenerationMode = "fast" | "balanced" | "pro";

export interface GenerationPreferences {
  get(scope: string): GenerationMode | undefined;
  save(scope: string, mode: GenerationMode): void;
}

export type GenerateLessonRequest = Readonly<{
  courseId: string;
  lessonId: string;
  generationMode?: GenerationMode;
}>;
