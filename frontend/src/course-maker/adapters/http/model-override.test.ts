import { describe, expect, it } from "vitest";
import { BrowserModelPreferences } from "../persistence/browser-model-preferences";
import { withModelOverride } from "./model-override";
import type { HttpTransport } from "./course-backend";

describe("general model preference", () => {
  it("persists the choice and sends the current choice on subsequent requests", async () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
    };
    const preferences = new BrowserModelPreferences(storage);
    const requests: RequestInit[] = [];
    const transport: HttpTransport = async (_url, init) => {
      requests.push(init ?? {});
      return new Response("{}");
    };
    const send = withModelOverride(transport, preferences);
    await send("/api/v1/courses", { method: "POST" });
    expect(requests[0].headers).toBeUndefined();
    preferences.save("anthropic/claude-opus-5.5:fast");
    await send("/api/v1/lessons/lesson_test/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ animatorModel: "openai/gpt-6-luna" }),
    });
    expect(new Headers(requests[1].headers).get("X-Generation-Model")).toBe(
      "anthropic/claude-opus-5.5:fast",
    );
    expect(new Headers(requests[1].headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(JSON.parse(requests[1].body as string).animatorModel).toBe(
      "openai/gpt-6-luna",
    );
    expect(new BrowserModelPreferences(storage).get()).toBe(
      "anthropic/claude-opus-5.5:fast",
    );
    preferences.save("");
    await send("/api/v1/lessons", {});
    expect(requests[2].headers).toBeUndefined();
  });
  it("ignores invalid saved choices and survives unavailable storage", () => {
    const invalid = new BrowserModelPreferences({
      getItem: () => "unknown",
      setItem: () => {},
    });
    expect(invalid.get()).toBe("");
    const unavailable = new BrowserModelPreferences({
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    unavailable.save("anthropic/claude-sonnet-5.5");
    expect(unavailable.get()).toBe("anthropic/claude-sonnet-5.5");
  });
});
