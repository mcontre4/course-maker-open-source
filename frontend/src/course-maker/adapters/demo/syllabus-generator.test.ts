import { describe, expect, it } from "vitest";
import { DemoSyllabusGenerator } from "./syllabus-generator";

describe("demo syllabus generation", () => {
  it("uses the description when choosing both the outline and cover", async () => {
    const result = await new DemoSyllabusGenerator().generate({
      title: "Coding basics",
      description: "Learn Python from scratch",
      duration: { mode: "total", hours: 7 },
    });
    expect(result.image).toBe("python");
    expect(result.chapters[0].lessons[0].title).toBe("Values and variables");
    expect(
      result.chapters
        .flatMap((chapter) => chapter.lessons)
        .reduce((minutes, lesson) => minutes + lesson.minutes, 0),
    ).toBe(420);
  });
});
