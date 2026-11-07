import { beforeEach, describe, expect, it } from "vitest";
import {
  BrowserLessonInteractives,
  browserLearnerInteractives,
} from "./browser-lesson-interactives";

const lessonId = "lesson_1";

describe("BrowserLessonInteractives", () => {
  let time: number;
  let next: number;
  let values: Map<string, string>;
  const storage = () => ({
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => void values.set(key, value),
  });
  const store = () =>
    new BrowserLessonInteractives(
      storage(),
      { next: () => String(++next) },
      () => new Date(time),
    );
  const finishBuild = () => {
    time += 60_000;
  };

  beforeEach(() => {
    time = Date.parse("2026-11-01T00:00:00Z");
    next = 0;
    values = new Map();
  });

  it("builds in the background and survives a reload", async () => {
    const created = await store().create({
      lessonId,
      brief: "A pendulum to swing",
    });
    expect(created.build?.stage).toBe("reading_lesson");
    expect(created.html).toBeNull();

    time += 2000;
    const midway = await store().get({ lessonId, id: created.id });
    expect(midway.build?.stage).toBe("designing");

    finishBuild();
    const done = await store().get({ lessonId, id: created.id });
    expect(done.build).toBeNull();
    expect(done.currentVersion).toBe(1);
    expect(done.title).toBe("Pendulum lab");
    expect(done.html).toContain("<canvas");
  });

  it("keeps learners on the published version while a new one is made", async () => {
    const app = store();
    const { id } = await app.create({ lessonId, brief: "A pendulum" });
    finishBuild();
    const built = await app.get({ lessonId, id });
    await app.setPublishedVersion({ lessonId, id, version: 1 });
    const learners = browserLearnerInteractives(app);
    const before = (await learners.list(lessonId))[0].html;

    await app.requestChange({
      lessonId,
      id,
      instruction: "Start on the Moon",
      expectedRevision: built.revision + 1,
    });
    finishBuild();
    const changed = await app.get({ lessonId, id });
    expect(changed.currentVersion).toBe(2);
    expect(changed.html).toContain('"gravity":1.62');
    expect((await learners.list(lessonId))[0]).toMatchObject({
      version: 1,
      html: before,
    });

    await app.setPublishedVersion({ lessonId, id, version: 2 });
    expect((await learners.list(lessonId))[0].html).toContain('"gravity":1.62');
  });

  it("goes back to an earlier version", async () => {
    const app = store();
    const { id } = await app.create({ lessonId, brief: "A pendulum" });
    finishBuild();
    const first = await app.get({ lessonId, id });
    await app.requestChange({
      lessonId,
      id,
      instruction: "Start on the Moon",
      expectedRevision: first.revision,
    });
    finishBuild();
    const second = await app.get({ lessonId, id });
    const restored = await app.restoreVersion({
      lessonId,
      id,
      version: 1,
      expectedRevision: second.revision,
    });
    expect(restored.currentVersion).toBe(1);
    expect(restored.html).toContain('"gravity":9.81');
    expect(restored.versions).toHaveLength(2);
  });

  it("builds a change on the version on screen, not one gone back from", async () => {
    const app = store();
    const { id } = await app.create({ lessonId, brief: "A pendulum" });
    finishBuild();
    const first = await app.get({ lessonId, id });
    await app.requestChange({
      lessonId,
      id,
      instruction: "Start on the Moon",
      expectedRevision: first.revision,
    });
    finishBuild();
    const second = await app.get({ lessonId, id });
    const restored = await app.restoreVersion({
      lessonId,
      id,
      version: 1,
      expectedRevision: second.revision,
    });
    await app.requestChange({
      lessonId,
      id,
      instruction: "Use a longer string",
      expectedRevision: restored.revision,
    });
    finishBuild();
    const third = await app.get({ lessonId, id });
    expect(third.currentVersion).toBe(3);
    expect(third.html).toContain('"gravity":9.81');
    expect(third.html).toContain('"length":2.2');
  });

  it("keeps working in this session when storage is full", async () => {
    const app = new BrowserLessonInteractives(
      {
        getItem: () => null,
        setItem: () => {
          throw new Error("Quota exceeded");
        },
      },
      { next: () => "1" },
      () => new Date(time),
    );
    const { id } = await app.create({ lessonId, brief: "A pendulum" });
    expect((await app.get({ lessonId, id })).brief).toBe("A pendulum");
  });

  it("turns a failed or stopped build into something to retry", async () => {
    const app = store();
    const { id } = await app.create({ lessonId, brief: "A pendulum #fail" });
    finishBuild();
    const failed = await app.get({ lessonId, id });
    expect(failed.failure?.message).toMatch(/stopped before/);
    expect(failed.currentVersion).toBeNull();

    const retried = await app.retryBuild({ lessonId, id });
    expect(retried.build?.request).toBe("A pendulum");
    expect(retried.failure).toBeNull();

    const stopped = await app.cancelBuild({ lessonId, id });
    expect(stopped.build).toBeNull();
    expect(stopped.failure?.message).toMatch(/You stopped/);
  });

  it("refuses a change based on an out-of-date copy", async () => {
    const app = store();
    const { id } = await app.create({ lessonId, brief: "A pendulum" });
    finishBuild();
    await expect(
      app.requestChange({
        lessonId,
        id,
        instruction: "Bigger",
        expectedRevision: 99,
      }),
    ).rejects.toThrow(/another tab/);
  });

  it("orders and removes interactives", async () => {
    const app = store();
    const one = await app.create({ lessonId, brief: "One" });
    const two = await app.create({ lessonId, brief: "Two" });
    const order = await app.reorder(lessonId, [two.id, one.id]);
    expect(order.map((item) => item.brief)).toEqual(["Two", "One"]);
    await app.remove({ lessonId, id: two.id });
    expect((await app.list(lessonId)).map((item) => item.brief)).toEqual([
      "One",
    ]);
  });

  it("limits how many a lesson can have", async () => {
    const app = store();
    for (let at = 0; at < 10; at++)
      await app.create({ lessonId, brief: `Idea ${at}` });
    await expect(app.create({ lessonId, brief: "Too many" })).rejects.toThrow(
      /up to 10/,
    );
  });
});
