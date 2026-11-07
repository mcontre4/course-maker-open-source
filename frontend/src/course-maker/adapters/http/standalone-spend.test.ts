import { expect, it } from "vitest";
import { HttpStandaloneLessons } from "./standalone-lessons";
import { MemoryStandaloneBackend } from "../../testing/standalone-backend";

it("loads lessons without requesting internal spend", async () => {
  const memory = new MemoryStandaloneBackend();
  const lesson = await memory.create({
    title: "Constitution",
    description: "Civics",
    minutes: 1,
  });
  const requests: string[] = [];
  const backend = new HttpStandaloneLessons(async (url) => {
    requests.push(url);
    return new Response(JSON.stringify(lesson));
  });
  const result = await backend.get(lesson.id);
  expect(result.id).toBe(lesson.id);
  expect(result.spend).toBeUndefined();
  expect(requests).toEqual([`/api/v1/lessons/${lesson.id}`]);
});
