import type { CourseSpendResponse } from "./dto";

export type LessonReference = Readonly<{
  lessonId: string;
  courseId?: string;
}>;
export type LessonDiagnostics = Readonly<{
  lessonId: string;
  courseId: string | null;
  title: string;
  spend: CourseSpendResponse;
  generationSeconds: number | null;
  generationActive: boolean;
}>;
export interface InternalTools {
  inspect(
    reference: LessonReference,
    key: string,
    refresh?: boolean,
  ): Promise<LessonDiagnostics>;
}

export function parseLessonReference(input: string): LessonReference {
  const value = input.trim();
  const id = /^lesson_[a-zA-Z0-9_-]+$/;
  if (id.test(value)) return { lessonId: value };
  let path: string;
  let courseQuery: string | null;
  try {
    const url = new URL(value, "https://lesson.local");
    if (!["http:", "https:"].includes(url.protocol)) throw new Error();
    path = decodeURIComponent(url.pathname);
    courseQuery = url.searchParams.get("course");
  } catch {
    throw new Error("Enter a lesson URL or lesson ID.");
  }
  const match = path.match(
    /^\/(?:watch\/)?(?:courses\/(course_[a-zA-Z0-9_-]+)\/)?lessons\/(lesson_[a-zA-Z0-9_-]+)(?:\/edit)?\/?$/,
  );
  if (!match) throw new Error("Enter a lesson URL or lesson ID.");
  const courseId = match[1] ?? courseQuery;
  if (courseId && !/^course_[a-zA-Z0-9_-]+$/.test(courseId))
    throw new Error("Enter a lesson URL or lesson ID.");
  return { lessonId: match[2], ...(courseId ? { courseId } : {}) };
}
