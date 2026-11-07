import type { LessonResponse } from "../../application/dto";

// Artifact readiness is independent of the learner's completion progress.
export function hasLessonArtifacts(lesson: LessonResponse): boolean {
  return Boolean(
    lesson.videoUrl || lesson.animation?.status === "animation_ready",
  );
}

export function hasFinishedVideo(lesson: LessonResponse): boolean {
  return Boolean(
    lesson.videoUrl ||
    (lesson.animation?.status === "animation_ready" &&
      lesson.animation.reviewStatus !== "pending"),
  );
}

export function lessonPlaybackUrl(
  lesson: LessonResponse,
  courseId?: string,
): string | null {
  if (lesson.videoUrl) return lesson.videoUrl;
  if (!lesson.animation || lesson.animation.status !== "animation_ready")
    return null;
  const base = courseId
    ? `/api/v1/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lesson.id)}`
    : `/api/v1/lessons/${encodeURIComponent(lesson.id)}`;
  return `${base}/video?v=${encodeURIComponent(lesson.animation.outputHash ?? lesson.animation.projectKey)}`;
}
