import { describe, expect, it } from "vitest";
import type { CourseResponse } from "../application/dto";
import type { PublishedLesson } from "../application/creators";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { durationLabel } from "./components";
import { continueItems, newestPublicLessons } from "./home-feed";

function course(
  id: string,
  lessonIds: readonly string[],
  options: Partial<Pick<CourseResponse, "status" | "completed">> = {},
) {
  return {
    id,
    title: "Course " + id,
    description: "",
    image: "python",
    status: "ready",
    completed: [],
    duration: { mode: "total", hours: 3 },
    chapters: [
      {
        lessons: lessonIds.map((lessonId) => ({
          id: lessonId,
          title: "Lesson " + lessonId,
        })),
      },
    ],
    ...options,
  } as unknown as CourseResponse;
}

function lesson(id: string, finished = false) {
  return {
    id,
    content: {
      title: "Lesson " + id,
      image: "story",
      minutes: 3,
      animation: finished
        ? { status: "succeeded", reviewStatus: "approved" }
        : null,
      videoUrl: finished ? "https://example.com/v.mp4" : null,
      plan: null,
      storyboard: null,
      alignment: null,
    },
  } as unknown as StandaloneLessonResponse;
}

function published(id: string, title: string, image = "story") {
  return {
    id,
    title,
    image,
    minutes: 1,
    videoUrl: null,
    courseId: null,
  } satisfies PublishedLesson;
}

describe("continueItems", () => {
  it("puts the most recently opened item first", () => {
    const items = continueItems(
      [course("a", ["1"]), course("b", ["2"])],
      [lesson("c")],
      [
        { itemId: "a", lastOpenedAt: "2026-11-01T09:00:00+00:00" },
        { itemId: "c", lastOpenedAt: "2026-11-01T10:00:00+00:00" },
      ],
    );
    expect(items.map((item) => item.id)).toEqual(["c", "a", "b"]);
  });

  it("orders by actual time when timestamps use different zones", () => {
    const items = continueItems(
      [course("a", ["1"]), course("b", ["2"])],
      [],
      [
        { itemId: "a", lastOpenedAt: "2026-11-01T10:00:00+05:00" },
        { itemId: "b", lastOpenedAt: "2026-11-01T09:00:00+00:00" },
      ],
    );
    expect(items.map((item) => item.id)).toEqual(["b", "a"]);
  });

  it("leaves finished courses out", () => {
    const items = continueItems(
      [course("done", ["1"], { completed: ["1"] }), course("open", ["2"])],
      [],
      [],
    );
    expect(items.map((item) => item.id)).toEqual(["open"]);
  });

  it("resumes a course at its first incomplete lesson with its progress", () => {
    const [item] = continueItems(
      [course("a", ["1", "2", "3"], { completed: ["1"] })],
      [],
      [],
    );
    expect(item).toMatchObject({
      to: "/courses/a/lessons/2",
      detail: "Next: Lesson 2",
      progress: { completed: 1, total: 3 },
      unfinished: true,
    });
  });

  it("sends a draft course to its syllabus for review", () => {
    const [item] = continueItems(
      [course("draft", [], { status: "draft" })],
      [],
      [],
    );
    expect(item).toMatchObject({
      to: "/courses/draft/syllabus",
      action: "Review syllabus",
      status: { label: "Ready for your review", tone: "attention" },
    });
  });

  it("gives a course without lessons no progress", () => {
    const [item] = continueItems([course("empty", [])], [], []);
    expect(item.progress).toBeUndefined();
  });

  it("gives standalone lessons no progress, since none is recorded", () => {
    const [item] = continueItems([], [lesson("a")], []);
    expect(item.progress).toBeUndefined();
    expect(item.to).toBe("/lessons/a");
  });

  it("lists never-opened finished lessons after unfinished work", () => {
    const items = continueItems(
      [course("draft", [], { status: "draft" })],
      [lesson("finished", true), lesson("working")],
      [],
    );
    expect(items.map((item) => item.id)).toEqual([
      "working",
      "draft",
      "finished",
    ]);
    expect(items.at(-1)?.unfinished).toBe(false);
  });

  it("ignores activity for items that no longer exist", () => {
    const items = continueItems(
      [course("a", ["1"])],
      [],
      [{ itemId: "gone", lastOpenedAt: "2026-11-01T09:00:00+00:00" }],
    );
    expect(items.map((item) => item.id)).toEqual(["a"]);
  });
});

describe("durationLabel", () => {
  it("uses singular words for a one-week, one-hour schedule", () => {
    const schedule = { mode: "weekly", weeks: 1, hoursPerWeek: 1 };
    expect(
      durationLabel({ duration: schedule } as unknown as CourseResponse),
    ).toBe("1 week · 1 hour / week");
  });

  it("uses plural words otherwise", () => {
    const schedule = { mode: "weekly", weeks: 4, hoursPerWeek: 2 };
    expect(
      durationLabel({ duration: schedule } as unknown as CourseResponse),
    ).toBe("4 weeks · 2 hours / week");
  });
});

describe("newestPublicLessons", () => {
  it("keeps one lesson per title, in newest-first order", () => {
    const lessons = newestPublicLessons([
      published("1", "Snakes"),
      published("2", "Snakes"),
      published("3", "Theranos"),
    ]);
    expect(lessons.map((item) => item.id)).toEqual(["1", "3"]);
  });

  it("prefers the original over a newer copy", () => {
    const lessons = newestPublicLessons([
      published("copy", "The origin of halloween-copy"),
      published("original", "The origin of halloween"),
    ]);
    expect(lessons.map((item) => item.id)).toEqual(["original"]);
  });

  it("prefers a version with artwork", () => {
    const lessons = newestPublicLessons([
      published("blank", "Muscles", ""),
      published("art", "Muscles", "story"),
    ]);
    expect(lessons.map((item) => item.id)).toEqual(["art"]);
  });

  it("keeps a copy when it is the only version", () => {
    const lessons = newestPublicLessons([published("copy", "Volcanoes copy")]);
    expect(lessons.map((item) => item.title)).toEqual(["Volcanoes copy"]);
  });

  it("does not mistake a title about copy for a duplicate", () => {
    const lessons = newestPublicLessons([
      published("1", "How to write copy"),
      published("2", "How to write"),
    ]);
    expect(lessons).toHaveLength(2);
  });
});
