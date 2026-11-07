import type { LessonResponse } from "./dto";
import type { GenerationMode } from "./generation-mode";
import {
  LessonQuizError,
  quizProblem,
  tidyQuestions,
  type LessonQuiz,
  type QuizQuestion,
} from "../domain/lesson-quiz";

export type { LessonQuiz, QuizQuestion };
// The interface layer reaches quiz rules through the application boundary.
export {
  LessonQuizError,
  blankQuestion,
  questionProblem,
  quizLimits,
  quizProblem,
  tidyQuestions,
} from "../domain/lesson-quiz";

/** Where a lesson's quiz is kept. */
export interface LessonQuizStore {
  get(lessonId: string): Promise<LessonQuiz | null>;
  save(quiz: LessonQuiz): Promise<void>;
}

/** Drafts questions from what the lesson teaches. */
export interface LessonQuizGenerator {
  generate(lesson: LessonResponse): Promise<readonly QuizQuestion[]>;
}

export class GetLessonQuiz {
  constructor(private readonly store: LessonQuizStore) {}
  execute(lessonId: string) {
    return this.store.get(lessonId);
  }
}

export class GenerateLessonQuiz {
  constructor(
    private readonly store: LessonQuizStore,
    private readonly generator: LessonQuizGenerator,
  ) {}
  async execute(
    lesson: LessonResponse,
    _mode?: GenerationMode,
    _onlyIfMissing?: boolean,
  ): Promise<LessonQuiz> {
    const questions = await this.generator.generate(lesson);
    const problem = quizProblem(questions);
    if (problem) throw new LessonQuizError(problem);
    const quiz: LessonQuiz = {
      lessonId: lesson.id,
      questions,
      origin: "generated",
    };
    await this.store.save(quiz);
    return quiz;
  }
}

export class SaveLessonQuiz {
  constructor(private readonly store: LessonQuizStore) {}
  async execute(request: {
    lessonId: string;
    questions: readonly QuizQuestion[];
    expectedRevision?: number;
  }): Promise<LessonQuiz> {
    const questions = tidyQuestions(request.questions);
    const problem = quizProblem(questions);
    if (problem) throw new LessonQuizError(problem);
    const quiz: LessonQuiz = {
      lessonId: request.lessonId,
      questions,
      origin: "edited",
    };
    await this.store.save(quiz);
    return quiz;
  }
}

export interface LessonQuizApplication {
  serverGenerated?: boolean;
  get: Pick<GetLessonQuiz, "execute">;
  generate: Pick<GenerateLessonQuiz, "execute">;
  save: Pick<SaveLessonQuiz, "execute">;
}

export interface LessonQuizBackend {
  get(lessonId: string): Promise<LessonQuiz | null>;
  save(request: {
    lessonId: string;
    questions: readonly QuizQuestion[];
    expectedRevision?: number;
  }): Promise<LessonQuiz>;
  generate(
    lessonId: string,
    mode?: GenerationMode,
    onlyIfMissing?: boolean,
  ): Promise<LessonQuiz>;
}

export function createServerLessonQuizApplication(
  backend: LessonQuizBackend,
): LessonQuizApplication {
  return {
    serverGenerated: true,
    get: { execute: (id) => backend.get(id) },
    generate: {
      execute: (lesson, mode, onlyIfMissing) =>
        backend.generate(lesson.id, mode, onlyIfMissing),
    },
    save: { execute: (request) => backend.save(request) },
  };
}

export type LearnerQuiz = Readonly<{
  lessonId: string;
  revision: number;
  questions: readonly Readonly<{
    id: string;
    kind: "multiple_choice";
    prompt: string;
    options: readonly string[];
  }>[];
}>;

export type LessonQuizAttempt = Readonly<{
  id: string;
  quizRevision: number;
  answers: readonly number[];
  score: number;
  total: number;
  passed: boolean;
  submittedAt: string;
  feedback: readonly Readonly<{
    questionId: string;
    correct: boolean;
    explanation: string;
  }>[];
}>;

export interface LearnerQuizApplication {
  get(lessonId: string): Promise<LearnerQuiz | null>;
  submit(
    lessonId: string,
    quizRevision: number,
    answers: readonly number[],
  ): Promise<LessonQuizAttempt>;
  attempts(lessonId: string): Promise<readonly LessonQuizAttempt[]>;
}

export function createLessonQuizApplication(
  store: LessonQuizStore,
  generator: LessonQuizGenerator,
): LessonQuizApplication {
  return {
    get: new GetLessonQuiz(store),
    generate: new GenerateLessonQuiz(store, generator),
    save: new SaveLessonQuiz(store),
  };
}
