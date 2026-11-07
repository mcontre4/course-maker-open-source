import { describe, expect, it } from "vitest";
import { HttpStyleBackend } from "./style";
import { HttpCourseBackend, type HttpTransport } from "./course-backend";
import { HttpStandaloneLessons } from "./standalone-lessons";

describe("style HTTP boundary", () => {
  it("maps narrator previews without exposing provider credentials", async () => {
    const requests: { url: string; init?: RequestInit }[] = [];
    const transport: HttpTransport = async (url, init) => {
      requests.push({ url, init });
      return new Response(
        JSON.stringify({
          items: [
            {
              id: "friendly",
              name: "Friendly",
              description: "Warm",
              previewUrl: "https://example.com/sample.mp3",
              labels: ["language: en"],
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    };
    const backend = new HttpStyleBackend(
      transport,
      new HttpCourseBackend(transport),
      new HttpStandaloneLessons(transport),
    );
    const voices = await backend.voices();
    expect(voices[0].previewUrl).toBe("https://example.com/sample.mp3");
    expect(requests[0].url).toBe("/api/v1/voices");
    expect(requests[0].init?.headers).toBeUndefined();
  });

  it("keeps server errors actionable", async () => {
    const transport: HttpTransport = async () =>
      new Response(
        JSON.stringify({ detail: "Style changed; reload before saving" }),
        { status: 409 },
      );
    const backend = new HttpStyleBackend(
      transport,
      new HttpCourseBackend(transport),
      new HttpStandaloneLessons(transport),
    );
    await expect(
      backend.update({
        id: "lesson_one",
        kind: "lesson",
        expectedVersion: 1,
        style: { description: "Warm", audience: "", voiceId: "" },
        generationMode: "fast",
      }),
    ).rejects.toThrow("Style changed; reload before saving");
  });
});
