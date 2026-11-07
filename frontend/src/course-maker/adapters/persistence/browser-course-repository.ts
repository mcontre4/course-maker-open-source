import { persisted } from "./storage-schema";
import type { CourseRepository } from "../../application/ports";
import { CourseError, validateCourse } from "../../domain/course";
import type { Course } from "../../domain/course";

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** Browser details stay in this outgoing adapter; inject Storage or an in-memory fake. */
export class BrowserCourseRepository implements CourseRepository {
  private readonly key = "course-maker:v1";
  constructor(
    private readonly storage: KeyValueStorage,
    private readonly initialCourses: readonly Course[],
  ) {}

  private read(): readonly Course[] {
    let raw: string | null;
    try {
      raw = this.storage.getItem(this.key);
    } catch {
      throw new CourseError(
        "Browser storage is unavailable. Allow site storage to use this demo.",
      );
    }
    try {
      const courses =
        raw === null
          ? structuredClone(this.initialCourses)
          : persisted.parse(JSON.parse(raw)).courses;
      courses.forEach(validateCourse);
      if (new Set(courses.map((course) => course.id)).size !== courses.length)
        throw new Error("Duplicate course identifiers");
      return courses;
    } catch {
      throw new CourseError(
        "Saved demo data could not be read. Clear this site’s course-maker:v1 storage to start fresh.",
      );
    }
  }
  async list(): Promise<readonly Course[]> {
    return this.read();
  }
  async getById(id: string): Promise<Course | null> {
    return this.read().find((c) => c.id === id) ?? null;
  }
  async save(course: Course): Promise<void> {
    validateCourse(course);
    const courses = this.read();
    const next = courses.some((c) => c.id === course.id)
      ? courses.map((c) => (c.id === course.id ? course : c))
      : [...courses, course];
    try {
      this.storage.setItem(
        this.key,
        JSON.stringify({ version: 1, courses: next }),
      );
    } catch {
      throw new CourseError(
        "Your changes could not be saved. Check that browser storage has space and is enabled.",
      );
    }
  }
}
