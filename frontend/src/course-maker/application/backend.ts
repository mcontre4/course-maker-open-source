import type { GenerateLessonRequest } from "./generation-mode";
import type {
  CourseResponse,
  CreateCourseRequest,
  EditTopicRequest,
  GenerateSyllabusRequest,
  QuizResultResponse,
} from "./dto";
import { validateDetails, CourseError } from "../domain/course";

export interface CourseBackend {
  refreshSpend?(id: string): Promise<CourseResponse>;
  generateLesson(request: GenerateLessonRequest): Promise<CourseResponse>;
  list(): Promise<readonly CourseResponse[]>;
  get(id: string): Promise<CourseResponse>;
  create(request: CreateCourseRequest): Promise<CourseResponse>;
  update?(id: string, request: CreateCourseRequest): Promise<CourseResponse>;
  generate(request: GenerateSyllabusRequest): Promise<CourseResponse>;
  edit(request: EditTopicRequest): Promise<CourseResponse>;
  approve(id: string): Promise<CourseResponse>;
  review(
    request: Readonly<{ courseId: string; lessonId: string }>,
  ): Promise<CourseResponse>;
  submit(
    request: Readonly<{
      courseId: string;
      lessonId: string;
      answers: readonly number[];
    }>,
  ): Promise<QuizResultResponse>;
}

export class RefreshApiSpend {
  constructor(private readonly backend: CourseBackend) {}
  execute(id: string) {
    if (!this.backend.refreshSpend) return this.backend.get(id);
    return this.backend.refreshSpend(id);
  }
}

export class ListApiCourses {
  constructor(private readonly backend: CourseBackend) {}
  execute() {
    return this.backend.list();
  }
}
export class GetApiCourse {
  constructor(private readonly backend: CourseBackend) {}
  execute(id: string) {
    return this.backend.get(id);
  }
}
export class CreateApiCourse {
  constructor(private readonly backend: CourseBackend) {}
  async execute(request: CreateCourseRequest): Promise<CourseResponse> {
    validateDetails(request);
    return this.backend.create(request);
  }
}
export class GenerateSyllabus {
  constructor(private readonly backend: CourseBackend) {}
  execute(request: GenerateSyllabusRequest) {
    if (!request.message.trim() || request.message.length > 20000)
      throw new CourseError("Enter a message of up to 20,000 characters.");
    return this.backend.generate(request);
  }
}
export class EditApiTopic {
  constructor(private readonly backend: CourseBackend) {}
  execute(request: EditTopicRequest) {
    return this.backend.edit(request);
  }
}
export class ApproveApiSyllabus {
  constructor(private readonly backend: CourseBackend) {}
  execute(id: string) {
    return this.backend.approve(id);
  }
}
export class ReviewApiLesson {
  constructor(private readonly backend: CourseBackend) {}
  execute(request: Readonly<{ courseId: string; lessonId: string }>) {
    return this.backend.review(request);
  }
}
export class SubmitApiQuiz {
  constructor(private readonly backend: CourseBackend) {}
  execute(
    request: Readonly<{
      courseId: string;
      lessonId: string;
      answers: readonly number[];
    }>,
  ) {
    return this.backend.submit(request);
  }
}

export function isCourseConflict(error: unknown): boolean {
  return error instanceof Error && "kind" in error && error.kind === "conflict";
}

export class GenerateApiLesson {
  constructor(private readonly backend: CourseBackend) {}
  execute(request: GenerateLessonRequest) {
    return this.backend.generateLesson(request);
  }
}

export class SaveApiCourseDraft {
  constructor(private readonly backend: CourseBackend) {}
  async execute(
    request: CreateCourseRequest & { id?: string },
  ): Promise<CourseResponse> {
    validateDetails(request);
    const { id, ...details } = request;
    if (!id) return this.backend.create(details);
    if (!this.backend.update) throw new Error("Draft updates are unavailable.");
    return this.backend.update(id, details);
  }
}
