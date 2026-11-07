import { HttpInternalTools } from "./adapters/http/internal-tools";
import { CancelGeneration } from "./application/cancel-generation";
import { HttpGenerationCancellation } from "./adapters/http/cancel-generation";
import { HttpLessonPlayback } from "./adapters/http/lesson-playback";
import { SelectLessonPlayback } from "./application/lesson-playback";
import { HttpThumbnails } from "./adapters/http/thumbnails";
import { GenerateThumbnail } from "./application/thumbnails";
import { HttpCourseMedia } from "./adapters/http/media";
import { AdvanceCourseMedia } from "./application/media";
import { HttpStyleBackend } from "./adapters/http/style";
import { ListVoices, UpdateStyle } from "./application/style";
import { HttpStandaloneLessons } from "./adapters/http/standalone-lessons";
import {
  ListStandaloneLessons,
  GetStandaloneLesson,
  CreateStandaloneLesson,
  UpdateStandaloneLesson,
  CopyLesson,
  SaveStandaloneOutline,
  SaveStandaloneScript,
  PrepareStandaloneScript,
  PlanStandaloneLesson,
  AdvanceStandaloneLesson,
  RefreshStandaloneSpend,
} from "./application/standalone-lessons";
import {
  ApproveSyllabus,
  CreateCourse,
  SaveCourseDraft,
  GenerateDemoSyllabus,
  EditSyllabusTopic,
  GetCourse,
  ListCourses,
  ReviewLesson,
  SubmitQuiz,
} from "./application/use-cases";
import type { CourseApplication } from "./application/use-cases";
import type { IdGenerator } from "./application/ports";
import { BrowserCourseRepository } from "./adapters/persistence/browser-course-repository";
import type { KeyValueStorage } from "./adapters/persistence/browser-course-repository";
import { DemoSyllabusGenerator } from "./adapters/demo/syllabus-generator";
import { DemoQuizGenerator } from "./adapters/demo/quiz-generator";
import { createDemoCourses } from "./adapters/demo/seed-courses";
import {
  HttpCourseBackend,
  type HttpTransport,
} from "./adapters/http/course-backend";
import type { CourseBackend } from "./application/backend";
import {
  GenerateApiLesson,
  RefreshApiSpend,
  ApproveApiSyllabus,
  CreateApiCourse,
  SaveApiCourseDraft,
  EditApiTopic,
  GenerateSyllabus,
  GetApiCourse,
  ListApiCourses,
  ReviewApiLesson,
  SubmitApiQuiz,
} from "./application/backend";

import {
  createLessonQuizApplication,
  createServerLessonQuizApplication,
} from "./application/lesson-quizzes";
import {
  HttpLessonQuizzes,
  HttpLearnerQuizzes,
} from "./adapters/http/lesson-quizzes";
import { OutlineQuizGenerator } from "./adapters/demo/lesson-quiz-generator";
import { BrowserLessonQuizStore } from "./adapters/persistence/browser-lesson-quizzes";
import { createLessonInteractiveApplication } from "./application/lesson-interactives";
import {
  BrowserLessonInteractives,
  browserLearnerInteractives,
} from "./adapters/persistence/browser-lesson-interactives";
import { HttpCreators } from "./adapters/http/creators";
import {
  HttpLessonInteractives,
  HttpLearnerInteractives,
} from "./adapters/http/lesson-interactives";
import { HttpLearningActivity } from "./adapters/http/learning-activity";
import { HttpGuides } from "./adapters/http/guides";
import { HttpCredits } from "./adapters/http/credits";
import { DemoCredits } from "./adapters/demo/credits";

/** Interactive storage and sample builds for demo mode. */
export function createInteractiveApplications(
  storage: KeyValueStorage,
  ids: IdGenerator,
  now: () => Date,
): Pick<CourseApplication, "interactives" | "learnerInteractives"> {
  const store = new BrowserLessonInteractives(storage, ids, now);
  return {
    interactives: createLessonInteractiveApplication(store),
    learnerInteractives: browserLearnerInteractives(store),
  };
}

/** Browser-only credits and checkout for demo mode. */
export function createDemoCreditsApplication(
  storage: KeyValueStorage,
  ids: IdGenerator,
  now: () => Date,
): Pick<CourseApplication, "credits"> {
  return { credits: new DemoCredits(storage, ids, now) };
}

export function createApiCourseApplication(
  transport: HttpTransport,
): CourseApplication {
  const backend = new HttpStandaloneLessons(transport);
  const courses = new HttpCourseBackend(transport);
  const styles = new HttpStyleBackend(transport, courses, backend);
  return {
    ...createBackendCourseApplication(courses),
    internalTools: new HttpInternalTools(transport),
    quizzes: createServerLessonQuizApplication(
      new HttpLessonQuizzes(transport),
    ),
    learnerQuizzes: new HttpLearnerQuizzes(transport),
    interactives: createLessonInteractiveApplication(
      new HttpLessonInteractives(transport),
    ),
    learnerInteractives: new HttpLearnerInteractives(transport),
    cancelGeneration: new CancelGeneration(
      new HttpGenerationCancellation(transport),
    ),
    playback: new SelectLessonPlayback(new HttpLessonPlayback(transport)),
    creators: new HttpCreators(transport),
    credits: new HttpCredits(transport),
    learningActivity: new HttpLearningActivity(transport),
    guides: new HttpGuides(transport),
    thumbnails: new GenerateThumbnail(
      new HttpThumbnails(transport, courses, backend),
    ),
    styles: { voices: new ListVoices(styles), update: new UpdateStyle(styles) },
    generateMedia: new AdvanceCourseMedia(
      new HttpCourseMedia(transport, courses),
    ),
    lessons: {
      list: new ListStandaloneLessons(backend),
      get: new GetStandaloneLesson(backend),
      create: new CreateStandaloneLesson(backend),
      update: new UpdateStandaloneLesson(backend),
      copy: new CopyLesson(backend),
      saveOutline: new SaveStandaloneOutline(backend),
      saveScript: new SaveStandaloneScript(backend),
      prepareScript: new PrepareStandaloneScript(backend),
      plan: new PlanStandaloneLesson(backend),
      advance: new AdvanceStandaloneLesson(backend),
      refreshSpend: new RefreshStandaloneSpend(backend),
    },
  };
}

export function createBackendCourseApplication(
  backend: CourseBackend,
): CourseApplication {
  return {
    listCourses: new ListApiCourses(backend),
    refreshSpend: new RefreshApiSpend(backend),
    getCourse: new GetApiCourse(backend),
    createCourse: new CreateApiCourse(backend),
    saveCourseDraft: new SaveApiCourseDraft(backend),
    generateSyllabus: new GenerateSyllabus(backend),
    generateLesson: new GenerateApiLesson(backend),
    editTopic: new EditApiTopic(backend),
    approveSyllabus: new ApproveApiSyllabus(backend),
    reviewLesson: new ReviewApiLesson(backend),
    submitQuiz: new SubmitApiQuiz(backend),
  };
}

export function createCourseApplication(
  storage: KeyValueStorage,
  ids: IdGenerator,
): CourseApplication {
  const repository = new BrowserCourseRepository(storage, createDemoCourses());
  return {
    listCourses: new ListCourses(repository),
    saveCourseDraft: new SaveCourseDraft(repository, ids),
    buildCourseDraft: new GenerateDemoSyllabus(
      repository,
      new DemoSyllabusGenerator(),
    ),
    getCourse: new GetCourse(repository),
    createCourse: new CreateCourse(
      repository,
      new DemoSyllabusGenerator(),
      ids,
    ),
    editTopic: new EditSyllabusTopic(repository),
    approveSyllabus: new ApproveSyllabus(repository, new DemoQuizGenerator()),
    reviewLesson: new ReviewLesson(repository),
    submitQuiz: new SubmitQuiz(repository),
  };
}
