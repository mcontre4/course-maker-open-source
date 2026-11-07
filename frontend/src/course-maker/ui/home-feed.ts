import type { CourseResponse } from "../application/dto";
import type { PublishedLesson } from "../application/creators";
import type { LearningActivityItem } from "../application/learning-activity";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { durationLabel } from "./components";
import {
  isFinishedLesson,
  lessonWorkflowStatus,
  lessonWorkflowTone,
} from "./lesson-workflow";

export type HomeItem = Readonly<{
  id: string;
  title: string;
  image: string;
  variant: "course" | "lesson";
  to: string;
  action: string;
  detail: string;
  unfinished: boolean;
  progress?: Readonly<{ completed: number; total: number }>;
  status?: Readonly<{ label: string; tone: string }>;
}>;

function courseItem(course: CourseResponse): HomeItem {
  const lessons = course.chapters.flatMap((chapter) => chapter.lessons);
  const next = lessons.find((item) => !course.completed.includes(item.id));
  return {
    id: course.id,
    title: course.title,
    image: course.image,
    variant: "course",
    to: next
      ? "/courses/" + course.id + "/lessons/" + next.id
      : "/courses/" + course.id + "/syllabus",
    action: "Continue learning",
    detail: next ? "Next: " + next.title : durationLabel(course),
    unfinished: true,
    ...(lessons.length
      ? {
          progress: {
            completed: course.completed.length,
            total: lessons.length,
          },
        }
      : {}),
  };
}

function draftItem(course: CourseResponse): HomeItem {
  return {
    id: course.id,
    title: course.title,
    image: course.image,
    variant: "course",
    to: "/courses/" + course.id + "/syllabus",
    action: "Review syllabus",
    detail: durationLabel(course),
    unfinished: true,
    status: { label: "Ready for your review", tone: "attention" },
  };
}

function lessonItem(lesson: StandaloneLessonResponse): HomeItem {
  return {
    id: lesson.id,
    title: lesson.content.title,
    image: lesson.content.image,
    variant: "lesson",
    to: "/lessons/" + lesson.id,
    action: "Open lesson",
    detail: lesson.content.minutes + " min lesson",
    unfinished: !isFinishedLesson(lesson),
    status: {
      label: lessonWorkflowStatus(lesson),
      tone: lessonWorkflowTone(lesson),
    },
  };
}

function isFinishedCourse(course: CourseResponse) {
  const lessons = course.chapters.flatMap((chapter) => chapter.lessons);
  return (
    lessons.length > 0 &&
    lessons.every((item) => course.completed.includes(item.id))
  );
}

/** Your own work, most recently opened first. Work never opened keeps a useful default order. */
export function continueItems(
  courses: readonly CourseResponse[],
  lessons: readonly StandaloneLessonResponse[],
  activity: readonly LearningActivityItem[],
): readonly HomeItem[] {
  const opened = new Map(
    activity.map((item) => [item.itemId, Date.parse(item.lastOpenedAt)]),
  );
  const items = [
    ...courses
      .filter((course) => course.status === "ready")
      .filter((course) => !isFinishedCourse(course))
      .map(courseItem),
    ...lessons.filter((lesson) => !isFinishedLesson(lesson)).map(lessonItem),
    ...courses.filter((course) => course.status === "draft").map(draftItem),
    ...lessons.filter(isFinishedLesson).map(lessonItem),
  ];
  return items.toSorted(
    (a, b) => (opened.get(b.id) ?? 0) - (opened.get(a.id) ?? 0),
  );
}

const copySuffix = /(?:-\s*copy|\s*\(copy\))$/i;

function titleKey(title: string) {
  return title.trim().replace(copySuffix, "").trim().toLocaleLowerCase();
}

/** One lesson per title, since copies of a lesson can all be published. */
export function newestPublicLessons(
  lessons: readonly PublishedLesson[],
): readonly PublishedLesson[] {
  const versions = new Map<string, PublishedLesson[]>();
  for (const lesson of lessons) {
    const key = titleKey(lesson.title);
    versions.set(key, [...(versions.get(key) ?? []), lesson]);
  }
  return [...versions.values()].map((group) => {
    const originals = group.filter((item) => !copySuffix.test(item.title));
    return originals.find((item) => item.image) ?? originals[0] ?? group[0];
  });
}
