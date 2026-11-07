import type { PublishedCourse, PublishedLesson } from "../application/creators";
import {
  courseTopics,
  matchesCourseSearch,
  textInSubtopic,
  textInTopic,
  type CourseTopic,
} from "./course-catalog";

function courseText(course: PublishedCourse) {
  return [
    course.title,
    course.description,
    ...course.lessons.map((lesson) => lesson.title),
  ].join(" ");
}

export function coursesInTopic(
  courses: readonly PublishedCourse[],
  topic: CourseTopic,
  subtopic?: string,
) {
  return courses.filter((course) =>
    subtopic
      ? textInSubtopic(courseText(course), subtopic)
      : textInTopic(courseText(course), topic),
  );
}

export function coursesWithoutTopic(courses: readonly PublishedCourse[]) {
  return courses.filter(
    (course) =>
      !courseTopics.some((topic) => textInTopic(courseText(course), topic)),
  );
}

// Lessons carry only a title, so they are filed under a topic by that title.
export function lessonsInTopic(
  lessons: readonly PublishedLesson[],
  topic: CourseTopic,
  subtopic?: string,
) {
  return lessons.filter((lesson) =>
    subtopic
      ? textInSubtopic(lesson.title, subtopic)
      : textInTopic(lesson.title, topic),
  );
}

export function lessonsWithoutTopic(lessons: readonly PublishedLesson[]) {
  return lessons.filter(
    (lesson) => !courseTopics.some((topic) => textInTopic(lesson.title, topic)),
  );
}

export function coursesMatchingSearch(
  courses: readonly PublishedCourse[],
  search: string,
) {
  return courses.filter((course) =>
    matchesCourseSearch(search, [courseText(course)]),
  );
}

export function courseMinutes(course: PublishedCourse) {
  return course.lessons.reduce((total, lesson) => total + lesson.minutes, 0);
}

export function countLabel(count: number, word: string) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}
