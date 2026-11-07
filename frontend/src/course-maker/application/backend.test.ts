import { describe, expect, it } from "vitest";
import { CreateApiCourse, GenerateSyllabus } from "./backend";
import { MemoryCourseBackend } from "../testing/course-backend";

describe("API syllabus use cases", () => {
  it("sends the original prompt and retains the saved draft if generation fails", async () => {
    const backend = new MemoryCourseBackend();
    backend.failGeneration = true;
    const prompt = "  Teach Python with a practical project.  ";
    const result = await new CreateApiCourse(backend).execute({
      title: "Python",
      description: prompt,
      duration: { mode: "total", hours: 2 },
    });
    expect(backend.created).toHaveLength(1);
    expect(backend.generated).toHaveLength(0);
    expect(result.chapters).toEqual([]);
    await expect(
      new GenerateSyllabus(backend).execute({
        courseId: result.id,
        message: prompt,
        expectedRevision: 0,
      }),
    ).rejects.toThrow("unavailable");
    expect((await backend.get()).id).toBe(result.id);
    backend.failGeneration = false;
    const recovered = await new GenerateSyllabus(backend).execute({
      courseId: result.id,
      message: prompt,
      expectedRevision: 0,
    });
    expect(recovered.chapters.length).toBeGreaterThan(0);
    expect(backend.created).toHaveLength(1);
  });
  it.each(["", "  ", "x".repeat(20001)])(
    "rejects an invalid follow-up before calling the backend",
    (message) => {
      const backend = new MemoryCourseBackend();
      expect(() =>
        new GenerateSyllabus(backend).execute({
          courseId: "course_test",
          message,
          expectedRevision: 1,
        }),
      ).toThrow();
      expect(backend.generated).toHaveLength(0);
    },
  );
});
