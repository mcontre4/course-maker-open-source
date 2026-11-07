export type LessonPlaybackRequest = Readonly<{
  lessonId: string;
  courseId?: string;
  sourceHash?: string;
}>;
export type LessonPlaybackResponse = Readonly<{
  sourceHash: string;
  videoReady: boolean;
  previewUrl: string;
  videoUrl: string;
}>;
export interface LessonPlayback {
  select(request: LessonPlaybackRequest): Promise<LessonPlaybackResponse>;
}
export class SelectLessonPlayback {
  constructor(private readonly playback: LessonPlayback) {}
  execute(request: LessonPlaybackRequest): Promise<LessonPlaybackResponse> {
    return this.playback.select(request);
  }
}
