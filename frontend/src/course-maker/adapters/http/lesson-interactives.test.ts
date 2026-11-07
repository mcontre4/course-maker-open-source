import { describe, expect, it } from "vitest";
import {
  HttpLessonInteractives,
  HttpLearnerInteractives,
} from "./lesson-interactives";
import { createApiCourseApplication } from "../../composition";

const item = {
  id: "interactive_1",
  lessonId: "lesson_1",
  brief: "A lab",
  title: "Gravity",
  goal: "Explore gravity",
  prompts: ["Change gravity"],
  revision: 3,
  createdAt: "2026-11-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
  versions: [
    { number: 1, request: "A lab", createdAt: "2026-11-01T00:00:00Z" },
  ],
  currentVersion: 1,
  html: "<html>draft</html>",
  publishedVersion: null,
  publishedHtml: null,
  build: null,
  failure: null,
};

describe("interactive HTTP adapters", () => {
  it("maps every creator operation to the existing API contract", async () => {
    const calls: { path: string; init?: RequestInit }[] = [];
    const backend = new HttpLessonInteractives(async (path, init) => {
      calls.push({ path, init });
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      return Response.json(
        (path.endsWith("/interactives") && init?.method === "GET") ||
          path.endsWith("/order")
          ? { items: [item] }
          : item,
      );
    });
    const ref = { lessonId: "lesson /one", id: "interactive /one" };
    expect(await backend.list(ref.lessonId)).toEqual([item]);
    expect(await backend.get(ref)).toEqual(item);
    await backend.create({
      lessonId: ref.lessonId,
      brief: "A lab",
      generationMode: "fast",
    });
    await backend.requestChange({
      ...ref,
      instruction: "Add reset",
      expectedRevision: 3,
    });
    await backend.retryBuild(ref);
    await backend.cancelBuild(ref);
    await backend.saveDetails({
      ...ref,
      details: { title: "Title", goal: "", prompts: [] },
      expectedRevision: 3,
    });
    await backend.restoreVersion({ ...ref, version: 1, expectedRevision: 3 });
    await backend.setPublishedVersion({ ...ref, version: null });
    await backend.reorder(ref.lessonId, ["interactive_1"]);
    await backend.remove(ref);
    const root = "/api/v1/lessons/lesson%20%2Fone/interactives";
    const path = root + "/interactive%20%2Fone";
    expect(calls.map((c) => [c.path, c.init?.method])).toEqual([
      [root, "GET"],
      [path, "GET"],
      [root, "POST"],
      [path + "/changes", "POST"],
      [path + "/build/retry", "POST"],
      [path + "/build/cancel", "POST"],
      [path, "PATCH"],
      [path + "/versions/1/restore", "POST"],
      [path + "/published", "PUT"],
      [root + "/order", "PUT"],
      [path, "DELETE"],
    ]);
    expect(JSON.parse(String(calls[2].init?.body))).toEqual({
      brief: "A lab",
      generationMode: "fast",
    });
    expect(JSON.parse(String(calls[3].init?.body))).toEqual({
      instruction: "Add reset",
      expectedRevision: 3,
    });
    expect(JSON.parse(String(calls[6].init?.body))).toEqual({
      title: "Title",
      goal: "",
      prompts: [],
      expectedRevision: 3,
    });
    expect(JSON.parse(String(calls[8].init?.body))).toEqual({ version: null });
    expect(JSON.parse(String(calls[9].init?.body))).toEqual({
      ids: ["interactive_1"],
    });
    expect(calls.every((c) => c.init?.credentials === "same-origin")).toBe(
      true,
    );
  });

  it("uses the public endpoint and strips private extra fields", async () => {
    let path = "";
    const learner = new HttpLearnerInteractives(async (url) => {
      path = url;
      return Response.json({
        items: [{ ...item, version: 1, html: "published" }],
      });
    });
    const result = await learner.list("lesson /one");
    expect(path).toBe("/api/v1/published/lessons/lesson%20%2Fone/interactives");
    expect(result[0].html).toBe("published");
    expect(result[0]).not.toHaveProperty("brief");
    expect(result[0]).not.toHaveProperty("versions");
  });

  it("surfaces a server detail and rejects malformed responses", async () => {
    const backend = new HttpLessonInteractives(async () =>
      Response.json(
        { detail: "This interactive changed. Reload before continuing." },
        { status: 409 },
      ),
    );
    await expect(backend.get({ lessonId: "l", id: "i" })).rejects.toThrow(
      "Reload before continuing",
    );
    const fallback = new HttpLearnerInteractives(async () =>
      Response.json({}, { status: 500 }),
    );
    await expect(fallback.list("l")).rejects.toThrow(
      "The interactive request failed",
    );
    const malformed = new HttpLessonInteractives(async () =>
      Response.json({
        ...item,
        build: {
          request: "A lab",
          stage: "invented",
          startedAt: item.createdAt,
        },
      }),
    );
    await expect(malformed.get({ lessonId: "l", id: "i" })).rejects.toThrow();
  });

  it("production composition sends trimmed input through client rules to HTTP", async () => {
    const calls: unknown[] = [];
    const application = createApiCourseApplication(async (_path, init) => {
      calls.push(init?.body ? JSON.parse(String(init.body)) : undefined);
      return Response.json(item);
    });
    await application.interactives!.create({
      lessonId: item.lessonId,
      brief: "  A lab  ",
    });
    expect(calls).toEqual([{ brief: "A lab" }]);
    await expect(
      application.interactives!.create({
        lessonId: item.lessonId,
        brief: " ",
      }),
    ).rejects.toThrow();
    expect(calls).toHaveLength(1);
  });
});
