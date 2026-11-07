import { expect, it } from "vitest";
import { HttpStandaloneLessons } from "./standalone-lessons";
import { MemoryStandaloneBackend } from "../../testing/standalone-backend";
it("saves the edited outline through PUT without calling the planning endpoint", async () => {
  const memory = new MemoryStandaloneBackend();
  const draft = await memory.create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
  });
  const saved = await memory.plan({
    id: draft.id,
    expectedRevision: 0,
    message: "Plan",
  });
  const { lessonId: _id, sources: _sources, ...outline } = saved.content.plan!;
  const calls: { url: string; method: string | undefined; body: unknown }[] =
    [];
  const backend = new HttpStandaloneLessons(async (url, init) => {
    calls.push({
      url,
      method: init?.method,
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    if (url.endsWith("/spend")) return new Response("{}", { status: 503 });
    return new Response(JSON.stringify(saved));
  });
  const response = await backend.saveOutline({
    id: draft.id,
    expectedRevision: 1,
    outline,
  });
  expect(calls[0]).toEqual({
    url: `/api/v1/lessons/${draft.id}/outline`,
    method: "PUT",
    body: { expectedRevision: 1, outline },
  });
  expect(calls.some((call) => call.url.endsWith("/plan"))).toBe(false);
  expect(response.content.plan).toEqual(saved.content.plan);
});

it.each(["fast", "balanced", "pro"] as const)(
  "serializes %s for standalone outline, storyboard and animation",
  async (generationMode) => {
    const saved = await new MemoryStandaloneBackend().create({
      title: "Atoms",
      description: "Explain atoms",
      minutes: 3,
    });
    const calls: { url: string; body: unknown }[] = [];
    const backend = new HttpStandaloneLessons(async (url, init) => {
      calls.push({ url, body: JSON.parse(String(init?.body)) });
      return new Response(JSON.stringify(saved), { status: 200 });
    });
    await backend.plan({
      id: saved.id,
      expectedRevision: 0,
      message: "Explain atoms",
      generationMode,
    });
    for (const stage of ["storyboard", "animation", "video"] as const) {
      await backend.advance({
        id: saved.id,
        expectedRevision: 1,
        stage,
        generationMode,
        animatorModel: "anthropic/claude-sonnet-5.5",
        prepareElements: true,
        animationBackend: "direct",
      });
    }
    expect(calls.map((call) => call.body)).toEqual([
      { expectedRevision: 0, message: "Explain atoms", generationMode },
      { expectedRevision: 1, generationMode },
      {
        expectedRevision: 1,
        generationMode,
        animatorModel: "anthropic/claude-sonnet-5.5",
        prepareElements: true,
        animationBackend: "direct",
      },
      {
        expectedRevision: 1,
        generationMode,
        animatorModel: "anthropic/claude-sonnet-5.5",
        prepareElements: true,
        animationBackend: "direct",
      },
    ]);
  },
);

it("restores server activity and failures from an independent GET", async () => {
  const saved = await new MemoryStandaloneBackend().create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
  });
  const backend = new HttpStandaloneLessons(async (url) => {
    if (url.endsWith("/spend")) return new Response("{}", { status: 503 });
    return new Response(JSON.stringify(saved), {
      headers: {
        "X-Active-Operation": "video",
        "X-Operation-Error": "Saved failure",
      },
    });
  });
  expect(await backend.get(saved.id)).toMatchObject({
    activeOperation: "video",
    operationError: "Saved failure",
  });
});

it("persists flow and sends all automatic options to one endpoint", async () => {
  const draft = await new MemoryStandaloneBackend().create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
    flow: "automatic",
  });
  const calls: { url: string; body: unknown }[] = [];
  const backend = new HttpStandaloneLessons(async (url, init) => {
    if (url.endsWith("/spend")) return new Response("{}", { status: 503 });
    calls.push({ url, body: JSON.parse(String(init?.body)) });
    return new Response(JSON.stringify(draft));
  });
  const details = {
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
    flow: "automatic" as const,
  };
  expect((await backend.create(details)).flow).toBe("automatic");
  await backend.update({ ...details, id: draft.id, expectedRevision: 0 });
  await backend.advance({
    id: draft.id,
    expectedRevision: 1,
    stage: "automatic",
    message: "Teach beginners",
    generationMode: "fast",
    animatorModel: "anthropic/claude-sonnet-5.5",
    prepareElements: true,
    animationBackend: "direct",
  });
  expect(calls).toEqual([
    { url: "/api/v1/lessons", body: details },
    {
      url: "/api/v1/lessons/lesson_one",
      body: { ...details, expectedRevision: 0 },
    },
    {
      url: "/api/v1/lessons/lesson_one/automatic",
      body: {
        expectedRevision: 1,
        message: "Teach beginners",
        generationMode: "fast",
        animatorModel: "anthropic/claude-sonnet-5.5",
        prepareElements: true,
        animationBackend: "direct",
      },
    },
  ]);
});
