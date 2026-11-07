import { describe, expect, it } from "vitest";
import {
  ApproveSyllabus,
  CreateCourse,
  EditSyllabusTopic,
  GetCourse,
} from "./use-cases";
import type { CourseRepository, SyllabusGenerator } from "./ports";
import type { Course } from "../domain/course";
import { courseFixture } from "../testing/course-fixture";

class MemoryRepository implements CourseRepository {
  courses: Course[] = [];
  async list() {
    return this.courses;
  }
  async getById(id: string) {
    return this.courses.find((c) => c.id === id) ?? null;
  }
  async save(course: Course) {
    this.courses = [...this.courses.filter((c) => c.id !== course.id), course];
  }
}
const generator: SyllabusGenerator = {
  generate: async () => ({
    image: "python",
    chapters: courseFixture().chapters,
  }),
};
describe("course use cases", () => {
  it("rejects invalid generated quizzes without saving or approving the course", async () => {
    const repository = new MemoryRepository();
    await repository.save(courseFixture());
    const approve = new ApproveSyllabus(repository, {
      generate: async () => [],
    });
    await expect(approve.execute("course_test")).rejects.toThrow(
      "quiz is not ready",
    );
    expect(repository.courses[0].status).toBe("draft");
  });
  it("creates a draft using injected generation and identity, and returns no quiz answer keys", async () => {
    const repository = new MemoryRepository();
    const result = await new CreateCourse(repository, generator, {
      next: () => "course_deterministic",
    }).execute({
      title: " Python ",
      description: "Learn the basics",
      duration: { mode: "total", hours: 3 },
    });
    expect(result).toMatchObject({
      id: "course_deterministic",
      title: "Python",
      status: "draft",
    });
    expect(result.chapters[0].lessons[0].quiz[0]).not.toHaveProperty("answer");
    expect(repository.courses).toHaveLength(1);
  });
  it("edits and approves through ports, and rejects unknown courses", async () => {
    const repository = new MemoryRepository();
    await repository.save(courseFixture());
    await new EditSyllabusTopic(repository).execute({
      courseId: "course_test",
      lessonId: "lesson_1",
      topic: "Loops",
      operation: "add",
    });
    expect(repository.courses[0].chapters[0].lessons[0].topics).toContain(
      "Loops",
    );
    const quizzes = {
      generate: async () => courseFixture().chapters[0].lessons[0].quiz,
    };
    expect(
      (await new ApproveSyllabus(repository, quizzes).execute("course_test"))
        .status,
    ).toBe("ready");
    await expect(new GetCourse(repository).execute("missing")).rejects.toThrow(
      "could not be found",
    );
  });
});
