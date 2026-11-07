import { describe, expect, it } from "vitest";
import {
  approve,
  editTopic,
  gradeQuiz,
  markReviewed,
  totalHours,
} from "./course";
import { courseFixture } from "../testing/course-fixture";
describe("course rules", () => {
  it("cannot pass an empty quiz with a 0/0 score", () => {
    const course = markReviewed(approve(courseFixture()), "lesson_1");
    const emptyQuiz = {
      ...course,
      chapters: course.chapters.map((chapter) => ({
        ...chapter,
        lessons: chapter.lessons.map((lesson) => ({ ...lesson, quiz: [] })),
      })),
    };
    expect(() => gradeQuiz(emptyQuiz, "lesson_1", [])).toThrow(
      "quiz is not ready",
    );
  });
  it("cannot record video completion or grade a quiz before the video exists", () => {
    const original = approve(courseFixture());
    const missingVideo = {
      ...original,
      chapters: original.chapters.map((chapter) => ({
        ...chapter,
        lessons: chapter.lessons.map((lesson) => ({
          ...lesson,
          videoUrl: null,
        })),
      })),
    };
    expect(() => markReviewed(missingVideo, "lesson_1")).toThrow(
      "video is not ready",
    );
    expect(() => gradeQuiz(missingVideo, "lesson_1", [0])).toThrow(
      "video is not ready",
    );
  });
  it("accepts short courses and the maximum twelve-week schedule", () => {
    expect(totalHours({ mode: "total", hours: 2 })).toBe(2);
    expect(totalHours({ mode: "weekly", weeks: 12, hoursPerWeek: 40 })).toBe(
      480,
    );
  });
  it.each([
    { mode: "weekly" as const, weeks: 13, hoursPerWeek: 40 },
    { mode: "weekly" as const, weeks: 4.5, hoursPerWeek: 3 },
    { mode: "weekly" as const, weeks: 4, hoursPerWeek: 41 },
    { mode: "total" as const, hours: 481 },
    { mode: "total" as const, hours: Number.NaN },
  ])("rejects invalid duration %j", (duration) =>
    expect(() => totalHours(duration)).toThrow(),
  );
  it("keeps at least one topic and prevents edits after approval", () => {
    const original = courseFixture();
    const edited = editTopic(original, "lesson_1", "Variables", "remove");
    expect(original.chapters[0].lessons[0].topics).toHaveLength(2);
    expect(() => editTopic(edited, "lesson_1", "Strings", "remove")).toThrow(
      "Keep at least one",
    );
    expect(() =>
      editTopic(approve(original), "lesson_1", "Loops", "add"),
    ).toThrow("Only draft");
  });
  it("requires review and passing the quiz, and counts repeated completion once", () => {
    const course = approve(courseFixture());
    expect(() => gradeQuiz(course, "lesson_1", [0])).toThrow(
      "Watch the lesson video",
    );
    const reviewed = markReviewed(course, "lesson_1");
    const failed = gradeQuiz(reviewed, "lesson_1", [1]);
    expect(failed.course.completed).toHaveLength(0);
    expect(() => gradeQuiz(reviewed, "lesson_1", [])).toThrow(
      "Answer every question",
    );
    const passed = gradeQuiz(reviewed, "lesson_1", [0]);
    expect(passed.result.passed).toBe(true);
    expect(gradeQuiz(passed.course, "lesson_1", [0]).course.completed).toEqual([
      "lesson_1",
    ]);
  });
});
