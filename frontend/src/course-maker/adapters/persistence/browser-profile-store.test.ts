import { describe, expect, it } from "vitest";
import { BrowserProfileStore } from "./browser-profile-store";
import type { KeyValueStorage } from "./browser-course-repository";
class Storage implements KeyValueStorage {
  value: string | null = null;
  getItem() {
    return this.value;
  }
  setItem(_key: string, value: string) {
    this.value = value;
  }
}
describe("Browser profile storage", () => {
  it("round-trips name, email, and picture", () => {
    const storage = new Storage();
    const store = new BrowserProfileStore(storage);
    const profile = {
      name: "Alex",
      email: "alex@example.com",
      picture: "data:image/png;base64,aGVsbG8=",
    };
    store.save(profile);
    expect(new BrowserProfileStore(storage).load()).toEqual(profile);
  });
  it("recovers from missing, malformed, unsupported, and unsafe persisted data", () => {
    const storage = new Storage();
    for (const raw of [
      null,
      "{broken",
      JSON.stringify({ version: 2 }),
      JSON.stringify({
        version: 1,
        name: "Alex",
        email: "alex@example.com",
        picture: "javascript:alert(1)",
      }),
    ]) {
      storage.value = raw;
      expect(new BrowserProfileStore(storage).load()).toEqual({
        name: "Learner",
        email: "",
        picture: null,
      });
    }
  });
});
