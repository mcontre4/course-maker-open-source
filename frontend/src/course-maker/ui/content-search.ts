import type { Discovery } from "../application/creators";
import type { CourseResponse } from "../application/dto";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";

export type ContentMatch = Readonly<{
  id: string;
  kind: "course" | "lesson";
  title: string;
  detail: string;
  href: string;
  image: string;
}>;

export function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, " ");
}

export function searchContent(
  query: string,
  courses: readonly CourseResponse[],
  lessons: readonly StandaloneLessonResponse[],
  publicContent?: Discovery,
): ContentMatch[] {
  const normalized = normalizeSearch(query);
  if (!normalized) return [];
  const words = normalized.split(" ");
  const matches = new Map<string, ContentMatch>();
  const add = (match: ContentMatch, description = "") => {
    const text = normalizeSearch(match.title + " " + description);
    if (words.every((word) => text.includes(word)) && !matches.has(match.id))
      matches.set(match.id, match);
  };
  for (const course of courses) {
    add(
      {
        id: `course-${course.id}`,
        kind: "course",
        title: course.title,
        detail:
          course.status === "draft"
            ? "Course · Draft · In your library"
            : "Course · In your library",
        href: `/courses/${course.id}/syllabus`,
        image: course.image,
      },
      course.description,
    );
    for (const chapter of course.chapters)
      for (const lesson of chapter.lessons) {
        add({
          id: `lesson-${course.id}-${lesson.id}`,
          kind: "lesson",
          title: lesson.title,
          detail: `Lesson · ${course.title}`,
          href: `/courses/${course.id}/lessons/${lesson.id}`,
          image: lesson.image,
        });
      }
  }
  for (const lesson of lessons) {
    add({
      id: `lesson-${lesson.id}`,
      kind: "lesson",
      title: lesson.content.title,
      detail: "Lesson · In your library",
      href: `/lessons/${lesson.id}`,
      image: lesson.content.image,
    });
  }
  for (const course of publicContent?.courses ?? []) {
    const first = course.lessons[0];
    if (first)
      add(
        {
          id: `course-${course.id}`,
          kind: "course",
          title: course.title,
          detail: "Course · Published",
          href: `/watch/lessons/${first.id}?course=${course.id}`,
          image: course.image,
        },
        course.description,
      );
    for (const lesson of course.lessons) {
      add({
        id: `lesson-${course.id}-${lesson.id}`,
        kind: "lesson",
        title: lesson.title,
        detail: `Lesson · ${course.title}`,
        href: `/watch/lessons/${lesson.id}?course=${course.id}`,
        image: lesson.image,
      });
    }
  }
  for (const lesson of publicContent?.lessons ?? []) {
    const scope = lesson.courseId ? `${lesson.courseId}-` : "";
    add({
      id: `lesson-${scope}${lesson.id}`,
      kind: "lesson",
      title: lesson.title,
      detail: "Lesson · Published",
      href:
        `/watch/lessons/${lesson.id}` +
        (lesson.courseId ? `?course=${lesson.courseId}` : ""),
      image: lesson.image,
    });
  }
  const rank = (title: string) => {
    const value = normalizeSearch(title);
    return value === normalized
      ? 0
      : value.startsWith(normalized)
        ? 1
        : value.includes(normalized)
          ? 2
          : 3;
  };
  return [...matches.values()].sort((a, b) => rank(a.title) - rank(b.title));
}
