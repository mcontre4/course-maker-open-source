import { describe, expect, it } from "vitest";
import { HttpLearningActivity } from "./learning-activity";

describe("HttpLearningActivity", () => {
  it("reads recent activity from the API", async () => {
    const log = new HttpLearningActivity(
      async () =>
        new Response(
          JSON.stringify({
            items: [
              { itemId: "course_1", lastOpenedAt: "2026-11-01T09:00:00+00:00" },
            ],
          }),
        ),
    );
    await expect(log.recent()).resolves.toEqual([
      { itemId: "course_1", lastOpenedAt: "2026-11-01T09:00:00+00:00" },
    ]);
  });

  it("records an opened item with a PUT to its encoded id", async () => {
    const calls: [string, RequestInit | undefined][] = [];
    const log = new HttpLearningActivity(async (url, init) => {
      calls.push([String(url), init]);
      return new Response(null, { status: 204 });
    });
    await log.record("lesson_1");
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toBe("/api/v1/learning-activity/lesson_1");
    expect(calls[0][1]?.method).toBe("PUT");
  });

  it("reports a failed read", async () => {
    const log = new HttpLearningActivity(
      async () => new Response(null, { status: 500 }),
    );
    await expect(log.recent()).rejects.toThrow();
  });

  it("reports a failed record", async () => {
    const log = new HttpLearningActivity(
      async () => new Response(null, { status: 500 }),
    );
    await expect(log.record("lesson_1")).rejects.toThrow();
  });
});
