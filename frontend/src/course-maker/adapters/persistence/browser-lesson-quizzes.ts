import type { LessonQuizStore } from "../../application/lesson-quizzes";
import { quizProblem, type LessonQuiz } from "../../domain/lesson-quiz";
import type { KeyValueStorage } from "./browser-course-repository";

const key = (lessonId: string) => `course-maker:lesson-quiz:${lessonId}`;

/** Keeps quizzes in this browser until the server can store them. */
export class BrowserLessonQuizStore implements LessonQuizStore {
  private readonly memory = new Map<string, LessonQuiz>();
  constructor(private readonly storage: KeyValueStorage) {}

  async get(lessonId: string): Promise<LessonQuiz | null> {
    try {
      const raw = this.storage.getItem(key(lessonId));
      if (raw) {
        const parsed = JSON.parse(raw) as LessonQuiz;
        if (
          parsed.lessonId === lessonId &&
          Array.isArray(parsed.questions) &&
          !quizProblem(parsed.questions)
        )
          return parsed;
      }
    } catch {
      /* Fall back to what this session remembers. */
    }
    return this.memory.get(lessonId) ?? null;
  }

  async save(quiz: LessonQuiz): Promise<void> {
    this.memory.set(quiz.lessonId, quiz);
    try {
      this.storage.setItem(key(quiz.lessonId), JSON.stringify(quiz));
    } catch {
      /* Kept for this session only. */
    }
  }
}
