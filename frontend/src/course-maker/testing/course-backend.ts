import { styleFixture } from "./style-fixture";
import type { CourseBackend } from "../application/backend";
import type {
  CourseResponse,
  CreateCourseRequest,
  GenerateSyllabusRequest,
} from "../application/dto";
import { toResponse } from "../application/dto";
import { courseFixture } from "./course-fixture";

export class MemoryCourseBackend implements CourseBackend {
  async generateLesson() {
    return this.value;
  }
  value: CourseResponse = {
    ...toResponse(courseFixture()),
    messages: [],
    syllabus: { revision: 0, lessons: [], outcomes: [], warnings: [] },
  };
  created: CreateCourseRequest[] = [];
  generated: GenerateSyllabusRequest[] = [];
  failGeneration = false;
  conflictNext = false;
  pending?: Promise<void>;
  async list() {
    return this.created.length ? [this.value] : [];
  }
  async get() {
    return this.value;
  }
  async create(request: CreateCourseRequest) {
    this.created.push(request);
    this.value = {
      ...this.value,
      ...request,
      style: request.style ? styleFixture(request.style) : this.value.style,
      chapters: [],
      messages: [],
    };
    return this.value;
  }
  async update(_id: string, request: CreateCourseRequest) {
    this.value = {
      ...this.value,
      ...request,
      style: request.style
        ? styleFixture(request.style, (this.value.style?.version ?? 0) + 1)
        : this.value.style,
    };
    return this.value;
  }
  async generate(request: GenerateSyllabusRequest) {
    this.generated.push(request);
    if (this.pending) await this.pending;
    if (this.failGeneration)
      throw new Error("The guide is unavailable. Your draft is saved.");
    if (this.conflictNext) {
      this.conflictNext = false;
      this.value = {
        ...this.value,
        syllabus: {
          ...this.value.syllabus!,
          revision: request.expectedRevision + 1,
        },
      };
      throw Object.assign(
        new Error("Review the latest syllabus before sending again."),
        { kind: "conflict" },
      );
    }
    const chapters = toResponse(courseFixture()).chapters;
    this.value = {
      ...this.value,
      chapters,
      messages: [
        ...this.value.messages,
        { role: "learner", text: request.message },
        {
          role: "guide",
          text: "Updated your course. See https://docs.python.org/3/",
        },
      ],
      syllabus: {
        revision: request.expectedRevision + 1,
        outcomes: ["Write Python"],
        warnings: [],
        lessons: chapters.flatMap((ch) =>
          ch.lessons.map((ls) => ({
            id: ls.id,
            week: 1,
            objectives: ["Write Python"],
            videoMinutes: ls.minutes,
            practiceMinutes: 20,
            readingMinutes: 5,
            reviewMinutes: 5,
          })),
        ),
      },
    };
    return this.value;
  }
  async edit() {
    return this.value;
  }
  async approve() {
    this.value = { ...this.value, status: "ready" };
    return this.value;
  }
  async review() {
    return this.value;
  }
  async submit() {
    return {
      score: 1,
      total: 1,
      passed: true,
      feedback: [{ correct: true, explanation: "Correct" }],
    };
  }
}
