import { expect, it } from "vitest";
import { parseLessonReference } from "./internal-tools";

it.each([
  "lesson_one",
  " /lessons/lesson_one ",
  "https://app.example/lessons/lesson_one?tab=video#details",
  "https://app.example/watch/lessons/lesson_one",
  "/lessons/lesson_one/edit/",
])("parses lesson reference %s", (value) => {
  expect(parseLessonReference(value)).toEqual({ lessonId: "lesson_one" });
});
it("keeps the course scope when inspecting a course lesson URL", () => {
  expect(
    parseLessonReference(
      "https://app.example/courses/course_one/lessons/lesson_two",
    ),
  ).toEqual({
    courseId: "course_one",
    lessonId: "lesson_two",
  });
});
it("keeps the course scope from a public watch URL", () => {
  expect(
    parseLessonReference(
      "https://app.example/watch/lessons/lesson_two?course=course_one",
    ),
  ).toEqual({
    courseId: "course_one",
    lessonId: "lesson_two",
  });
});
it.each([
  "",
  "an idea for a lesson",
  "/lessons/new",
  "/courses/course_one",
  "javascript:alert(1)",
  "/lessons/lesson_one/unknown",
  "https://example.com/%ZZ",
])("rejects non-lesson reference %s", (value) => {
  expect(() => parseLessonReference(value)).toThrow(
    "Enter a lesson URL or lesson ID.",
  );
});
