import { describe, expect, it } from "vitest";
import { HttpGuides } from "./guides";

describe("guide HTTP errors", () => {
  it.each([500, 502, 503])(
    "handles a non-JSON %s response with a retryable message",
    async (status) => {
      const api = new HttpGuides(
        async () => new Response("Internal Server Error", { status }),
      );
      await expect(api.list("lesson_one", "lesson")).rejects.toMatchObject({
        message: "Your guide is temporarily unavailable. Please try again.",
        status,
      });
    },
  );
  it("keeps structured conflict errors for request recovery", async () => {
    const api = new HttpGuides(async () =>
      Response.json(
        { detail: "This chat changed. Reload it." },
        { status: 409 },
      ),
    );
    await expect(api.list("lesson_one", "lesson")).rejects.toMatchObject({
      message: "This chat changed. Reload it.",
      status: 409,
    });
  });
  it("handles malformed successful responses", async () => {
    const api = new HttpGuides(
      async () => new Response("<html>Proxy error</html>"),
    );
    await expect(api.list("lesson_one", "lesson")).rejects.toThrow(
      "Your guide returned an unreadable response. Please try again.",
    );
  });
  it("preserves the lost-response recovery instruction", async () => {
    const api = new HttpGuides(async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(api.list("lesson_one", "lesson")).rejects.toThrow(
      "Retry your message to check its saved result.",
    );
  });
});
