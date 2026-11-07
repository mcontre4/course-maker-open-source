import type {
  GenerationPreferences,
  GenerateLessonRequest,
} from "./generation-mode";
import type { LessonApplication } from "./standalone-lessons";
import {
  approve,
  CourseError,
  editTopic,
  gradeQuiz,
  markReviewed,
  validateDetails,
  validateCourse,
} from "../domain/course";
import type { Course } from "../domain/course";
import { toResponse } from "./dto";
import type {
  CreateCourseRequest,
  CourseResponse,
  EditTopicRequest,
  QuizResultResponse,
  GenerateSyllabusRequest,
} from "./dto";
import type {
  CourseRepository,
  IdGenerator,
  QuizGenerator,
  SyllabusGenerator,
} from "./ports";

async function requireCourse(
  repository: CourseRepository,
  id: string,
): Promise<Course> {
  const course = await repository.getById(id);
  if (!course) throw new CourseError("This course could not be found.");
  return course;
}
export class ListCourses {
  constructor(private readonly repository: CourseRepository) {}
  async execute(): Promise<readonly CourseResponse[]> {
    return (await this.repository.list()).map(toResponse);
  }
}
export class GetCourse {
  constructor(private readonly repository: CourseRepository) {}
  async execute(id: string): Promise<CourseResponse> {
    return toResponse(await requireCourse(this.repository, id));
  }
}
export class CreateCourse {
  constructor(
    private readonly repository: CourseRepository,
    private readonly generator: SyllabusGenerator,
    private readonly ids: IdGenerator,
  ) {}
  async execute(request: CreateCourseRequest): Promise<CourseResponse> {
    const details = {
      ...request,
      title: request.title.trim(),
      description: request.description.trim(),
      duration: { ...request.duration },
    };
    validateDetails(details);
    const generated = await this.generator.generate(details);
    const course: Course = {
      ...details,
      id: this.ids.next(),
      image: generated.image,
      status: "draft",
      chapters: generated.chapters,
      reviewed: [],
      completed: [],
      messages: [
        {
          role: "guide",
          text: "Here’s a starting outline. Review the lesson topics, remove anything you don’t need, or add what’s missing. You approve the plan before learning begins.",
        },
      ],
    };
    validateCourse(course);
    await this.repository.save(course);
    return toResponse(course);
  }
}
export class EditSyllabusTopic {
  constructor(private readonly repository: CourseRepository) {}
  async execute(request: EditTopicRequest): Promise<CourseResponse> {
    const original = await requireCourse(this.repository, request.courseId);
    const course = editTopic(
      original,
      request.lessonId,
      request.topic,
      request.operation,
    );
    const updated: Course = {
      ...course,
      messages: [
        ...course.messages,
        {
          role: "learner",
          text: `${request.operation === "add" ? "Add" : "Remove"}: ${request.topic}`,
        },
        {
          role: "guide",
          text: `Topic ${request.operation === "add" ? "added" : "removed"}. Review the updated outline before approving.`,
        },
      ],
    };
    await this.repository.save(updated);
    return toResponse(updated);
  }
}
export class ApproveSyllabus {
  constructor(
    private readonly repository: CourseRepository,
    private readonly quizzes: QuizGenerator,
  ) {}
  async execute(id: string): Promise<CourseResponse> {
    const original = await requireCourse(this.repository, id);
    if (original.status === "ready") return toResponse(original);
    const approved = approve(original);
    const chapters = await Promise.all(
      approved.chapters.map(async (chapter) => ({
        ...chapter,
        lessons: await Promise.all(
          chapter.lessons.map(async (lesson) => ({
            ...lesson,
            quiz: await this.quizzes.generate(lesson),
          })),
        ),
      })),
    );
    const course = { ...approved, chapters };
    validateCourse(course);
    await this.repository.save(course);
    return toResponse(course);
  }
}
export class ReviewLesson {
  constructor(private readonly repository: CourseRepository) {}
  async execute(
    request: Readonly<{ courseId: string; lessonId: string }>,
  ): Promise<CourseResponse> {
    const course = markReviewed(
      await requireCourse(this.repository, request.courseId),
      request.lessonId,
    );
    await this.repository.save(course);
    return toResponse(course);
  }
}
export class SubmitQuiz {
  constructor(private readonly repository: CourseRepository) {}
  async execute(
    request: Readonly<{
      courseId: string;
      lessonId: string;
      answers: readonly number[];
    }>,
  ): Promise<QuizResultResponse> {
    const { course, result } = gradeQuiz(
      await requireCourse(this.repository, request.courseId),
      request.lessonId,
      request.answers,
    );
    await this.repository.save(course);
    return result;
  }
}

// Inbound application port. React knows only these use-case contracts.
export interface CourseApplication {
  internalTools?: import("./internal-tools").InternalTools;
  cancelGeneration?: Pick<
    import("./cancel-generation").CancelGeneration,
    "execute"
  >;
  playback?: Pick<import("./lesson-playback").SelectLessonPlayback, "execute">;
  guides?: import("./guides").Guides;
  quizzes?: import("./lesson-quizzes").LessonQuizApplication;
  learnerQuizzes?: import("./lesson-quizzes").LearnerQuizApplication;
  interactives?: import("./lesson-interactives").LessonInteractiveApplication;
  learnerInteractives?: import("./lesson-interactives").LearnerInteractiveApplication;
  creators?: import("./creators").Creators;
  credits?: import("./credits").Credits;
  learningActivity?: import("./learning-activity").LearningActivityLog;
  thumbnails?: Pick<import("./thumbnails").GenerateThumbnail, "execute">;
  generateMedia?: Pick<import("./media").AdvanceCourseMedia, "execute">;
  styles?: import("./style").StyleApplication;
  generationPreferences?: GenerationPreferences;
  modelPreferences?: import("./model-preferences").ModelPreferences;
  buildCourseDraft?: {
    execute(request: GenerateSyllabusRequest): Promise<CourseResponse>;
  };
  lessons?: LessonApplication;
  refreshSpend?: { execute(id: string): Promise<CourseResponse> };
  generateLesson?: {
    execute(input: GenerateLessonRequest): Promise<CourseResponse>;
  };
  listCourses: Pick<ListCourses, "execute">;
  getCourse: Pick<GetCourse, "execute">;
  createCourse: Pick<CreateCourse, "execute">;
  saveCourseDraft?: {
    execute(
      request: CreateCourseRequest & { id?: string },
    ): Promise<CourseResponse>;
  };
  editTopic: Pick<EditSyllabusTopic, "execute">;
  approveSyllabus: Pick<ApproveSyllabus, "execute">;
  reviewLesson: Pick<ReviewLesson, "execute">;
  submitQuiz: Pick<SubmitQuiz, "execute">;
  generateSyllabus?: Readonly<{
    execute(request: GenerateSyllabusRequest): Promise<CourseResponse>;
  }>;
}

export class SaveCourseDraft {
  constructor(
    private readonly repository: CourseRepository,
    private readonly ids: IdGenerator,
  ) {}
  async execute(
    request: CreateCourseRequest & { id?: string },
  ): Promise<CourseResponse> {
    validateDetails(request);
    const previous = request.id
      ? await requireCourse(this.repository, request.id)
      : null;
    if (previous && previous.status !== "draft")
      throw new CourseError("Only drafts can be edited.");
    const course: Course = {
      ...(previous ?? {
        id: this.ids.next(),
        status: "draft",
        image: "abstract",
        chapters: [],
        reviewed: [],
        completed: [],
        messages: [],
      }),
      title: request.title.trim(),
      description: request.description.trim(),
      duration: request.duration,
    };
    await this.repository.save(course);
    return toResponse(course);
  }
}
export class GenerateDemoSyllabus {
  constructor(
    private readonly repository: CourseRepository,
    private readonly generator: SyllabusGenerator,
  ) {}
  async execute(request: GenerateSyllabusRequest): Promise<CourseResponse> {
    const original = await requireCourse(this.repository, request.courseId);
    const generated = await this.generator.generate(original);
    const updated = {
      ...original,
      chapters: generated.chapters,
      image: generated.image,
    };
    await this.repository.save(updated);
    return toResponse(updated);
  }
}
