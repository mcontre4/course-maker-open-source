import { SaveApiCourseDraft } from "../../application/backend";
import { describe, expect, it } from "vitest";
import { HttpCourseBackend } from "./course-backend";
import { toResponse } from "../../application/dto";
import { courseFixture } from "../../testing/course-fixture";

class RecordingHttp {
  calls: { url: string; init?: RequestInit }[] = [];
  constructor(
    private readonly responses: readonly { status?: number; body: unknown }[],
  ) {}
  send = async (url: string, init?: RequestInit) => {
    this.calls.push({ url, init });
    const next = this.responses[this.calls.length - 1];
    if (!next) throw new Error("Unexpected request");
    return new Response(JSON.stringify(next.body), {
      status: next.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  };
}
const apiCourse = () => ({
  ...toResponse(courseFixture()),
  messages: undefined,
  duration: { mode: "total", hours: 2, weeks: null, hoursPerWeek: null },
});
const apiSession = () => ({
  revision: 2,
  turns: [{ user: "Research Python", assistant: "Official sources" }],
  curriculum: {
    outcomes: ["Build a program"],
    warnings: [],
    chapters: [
      {
        lessons: [
          {
            lesson_id: "lesson_1",
            week: 1,
            objectives: ["Assign values"],
            video_minutes: 10,
            practice_minutes: 20,
            reading_minutes: 5,
            review_minutes: 5,
          },
        ],
      },
    ],
  },
});

describe("HTTP course adapter", () => {
  it("loads courses without requesting internal spend", async () => {
    const http = new RecordingHttp([
      { body: apiCourse() },
      { body: apiSession() },
    ]);
    const result = await new HttpCourseBackend(http.send).get("course_test");
    expect(result.id).toBe("course_test");
    expect(result.spend).toBeUndefined();
    expect(http.calls.map((call) => call.url)).toEqual([
      "/api/v1/courses/course_test",
      "/api/v1/courses/course_test/syllabus/session",
    ]);
  });
  it("restores server conversation and maps API curriculum into UI read models", async () => {
    const http = new RecordingHttp([
      { body: apiCourse() },
      { body: apiSession() },
    ]);
    const result = await new HttpCourseBackend(http.send).get("course_test");
    expect(result.messages).toEqual([
      { role: "learner", text: "Research Python" },
      { role: "guide", text: "Official sources" },
    ]);
    expect(result.syllabus?.revision).toBe(2);
    expect(result.syllabus?.lessons[0]).toMatchObject({
      id: "lesson_1",
      videoMinutes: 10,
      practiceMinutes: 20,
    });
    expect(result.duration).toEqual({ mode: "total", hours: 2 });
    expect(result.chapters[0].lessons[0].quiz[0]).not.toHaveProperty("answer");
  });
  it("sends exact follow-up text and revision without a browser API credential", async () => {
    const http = new RecordingHttp([
      { body: { course: apiCourse(), session: apiSession() } },
    ]);
    await new HttpCourseBackend(http.send).generate({
      courseId: "course_test",
      message: "  Add a project  ",
      expectedRevision: 1,
    });
    expect(http.calls[0].url).toBe(
      "/api/v1/courses/course_test/syllabus/generate",
    );
    expect(http.calls[0].init?.method).toBe("POST");
    expect(JSON.parse(http.calls[0].init?.body as string)).toEqual({
      message: "  Add a project  ",
      expectedRevision: 1,
    });
    expect(new Headers(http.calls[0].init?.headers).has("Authorization")).toBe(
      false,
    );
  });
  it.each([401, 503, 409])(
    "maps HTTP %s into useful application feedback",
    async (status) => {
      const http = new RecordingHttp([
        { status, body: { detail: "internal detail" } },
      ]);
      const request = new HttpCourseBackend(http.send).generate({
        courseId: "course_test",
        message: "More examples",
        expectedRevision: 0,
      });
      await expect(request).rejects.toThrow(
        status === 401
          ? /authorize/
          : status === 503
            ? /unavailable/
            : /changed/,
      );
    },
  );
  it("reads every server page instead of silently truncating the library", async () => {
    const http = new RecordingHttp([
      { body: { items: [apiCourse()], total: 2 } },
      { body: { items: [{ ...apiCourse(), id: "course_second" }], total: 2 } },
    ]);
    expect(await new HttpCourseBackend(http.send).list()).toHaveLength(2);
    expect(http.calls[1].url).toBe("/api/v1/courses?limit=100&offset=1");
  });
  it("routes lesson generation and preserves its complete teaching plan", async () => {
    const plan = {
      lessonId: "lesson_1",
      objectives: ["Explain force"],
      assumedKnowledge: ["Addition"],
      introducedKnowledge: ["Net force"],
      requiredFacts: ["Force changes velocity"],
      equations: ["F=ma"],
      misconceptions: [],
      scopeBoundaries: ["Constant mass"],
      beats: [
        {
          title: "Net force",
          purpose: "Combine forces",
          teachingNotes: "Add signed forces",
          concepts: ["Net force"],
          seconds: 300,
          checkQuestion: "7N minus 3N?",
          expectedAnswer: "4N",
        },
      ],
      examples: [{ problem: "Two pushes", steps: ["7 - 3"], result: "4 N" }],
      sources: [{ title: "Source", url: "https://example.com/physics" }],
    };
    const saved = apiCourse();
    const http = new RecordingHttp([
      {
        body: {
          ...saved,
          chapters: saved.chapters.map((ch) => ({
            ...ch,
            lessons: ch.lessons.map((ls) => ({ ...ls, plan })),
          })),
        },
      },
    ]);
    const result = await new HttpCourseBackend(http.send).generateLesson({
      courseId: "course_test",
      lessonId: "lesson_1",
    });
    expect(http.calls[0].url).toBe(
      "/api/v1/courses/course_test/lessons/generate",
    );
    expect(JSON.parse(String(http.calls[0].init?.body))).toEqual({
      lessonId: "lesson_1",
    });
    expect(result.chapters[0].lessons[0].plan).toEqual(plan);
  });
  it("does not retry failed lesson generation or substitute a demo plan", async () => {
    const http = new RecordingHttp([
      { status: 503, body: { detail: "Provider failed" } },
    ]);
    await expect(
      new HttpCourseBackend(http.send).generateLesson({
        courseId: "course_test",
        lessonId: "lesson_1",
      }),
    ).rejects.toThrow(/unavailable/);
    expect(http.calls).toHaveLength(1);
  });
  it("maps malformed successful responses to safe recovery feedback", async () => {
    const backend = new HttpCourseBackend(
      async () => new Response("<html>proxy error</html>"),
    );
    await expect(backend.list()).rejects.toThrow(/unreadable response/);
    const http = new RecordingHttp([
      { body: { items: [{ id: "invalid" }], total: 1 } },
    ]);
    await expect(new HttpCourseBackend(http.send).list()).rejects.toThrow(
      /unexpected response/,
    );
  });
});

it.each(["fast", "balanced", "pro"] as const)(
  "serializes %s for syllabus and course lesson generation",
  async (generationMode) => {
    const http = new RecordingHttp([
      { body: { course: apiCourse(), session: apiSession() } },
      { body: apiCourse() },
    ]);
    const backend = new HttpCourseBackend(http.send);
    await backend.generate({
      courseId: "course_test",
      message: "Teach me",
      expectedRevision: 0,
      generationMode,
    });
    await backend.generateLesson({
      courseId: "course_test",
      lessonId: "lesson_1",
      generationMode,
    });
    expect(
      http.calls.map(
        (call) => JSON.parse(String(call.init?.body)).generationMode,
      ),
    ).toEqual([generationMode, generationMode]);
  },
);

it("resaves a course draft without sending its URL identifier in the body", async () => {
  const http = new RecordingHttp([{ body: apiCourse() }]);
  const details = {
    title: "Updated title",
    description: "Updated description",
    duration: { mode: "total" as const, hours: 1 },
  };
  await new SaveApiCourseDraft(new HttpCourseBackend(http.send)).execute({
    id: "course_test",
    ...details,
  });
  expect(http.calls[0].url).toBe("/api/v1/courses/course_test");
  expect(http.calls[0].init?.method).toBe("PUT");
  expect(JSON.parse(String(http.calls[0].init?.body))).toEqual(details);
});
