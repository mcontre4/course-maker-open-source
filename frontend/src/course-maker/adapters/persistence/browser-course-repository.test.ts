import { describe, expect, it } from "vitest";
import { BrowserCourseRepository } from "./browser-course-repository";
import { courseFixture } from "../../testing/course-fixture";

describe("browser persistence adapter", () => {
  it("round-trips a saved course and preserves an intentional empty library", async () => {
    let raw: string | null = null;
    const storage = {
      getItem: () => raw,
      setItem: (_key: string, value: string) => {
        raw = value;
      },
    };
    const repository = new BrowserCourseRepository(storage, [courseFixture()]);
    await repository.save({ ...courseFixture(), title: "Updated title" });
    expect(
      (await new BrowserCourseRepository(storage, []).getById("course_test"))
        ?.title,
    ).toBe("Updated title");
    raw = JSON.stringify({ version: 1, courses: [] });
    expect(await repository.list()).toEqual([]);
  });
  it("reports corrupted data instead of silently discarding it", async () => {
    const repository = new BrowserCourseRepository(
      { getItem: () => "{broken", setItem: () => {} },
      [],
    );
    await expect(repository.list()).rejects.toThrow("could not be read");
  });
  it("reports a failed write instead of pretending progress was saved", async () => {
    const repository = new BrowserCourseRepository(
      {
        getItem: () => null,
        setItem: () => {
          throw new Error("Storage full");
        },
      },
      [],
    );
    await expect(repository.save(courseFixture())).rejects.toThrow(
      "could not be saved",
    );
  });
});
