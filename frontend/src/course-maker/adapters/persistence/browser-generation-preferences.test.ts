import { describe, expect, it } from "vitest";
import { BrowserGenerationPreferences } from "./browser-generation-preferences";

describe("Browser generation preferences", () => {
  it("persists valid modes independently by scope and ignores stale values", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
    };
    const first = new BrowserGenerationPreferences(storage);
    first.save("course:one", "pro");
    first.save("lesson:two", "fast");
    const restored = new BrowserGenerationPreferences(storage);
    expect(restored.get("course:one")).toBe("pro");
    expect(restored.get("lesson:two")).toBe("fast");
    expect(restored.get("missing")).toBeUndefined();
    values.set("course-maker:generation:v1:stale", "old-model");
    expect(restored.get("stale")).toBeUndefined();
  });
  it("keeps generation available when browser storage is blocked", () => {
    const preferences = new BrowserGenerationPreferences({
      getItem() {
        throw new Error("Blocked");
      },
      setItem() {
        throw new Error("Blocked");
      },
    });
    expect(preferences.get("course:one")).toBeUndefined();
    expect(() => preferences.save("course:one", "pro")).not.toThrow();
  });
});
