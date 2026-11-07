import { z } from "zod";
import type { HttpTransport } from "./course-backend";
import type {
  LessonQuizBackend,
  LearnerQuizApplication,
} from "../../application/lesson-quizzes";
import type { GenerationMode } from "../../application/generation-mode";

const question = z.object({
  id: z.string(),
  kind: z.literal("multiple_choice"),
  prompt: z.string(),
  options: z.array(z.string()),
});
const learnerQuiz = z.object({
  lessonId: z.string(),
  revision: z.number().int(),
  questions: z.array(question),
});
const authorQuiz = learnerQuiz.extend({
  origin: z.enum(["generated", "edited"]),
  questions: z.array(
    question.extend({
      correctIndex: z.number().int(),
      explanation: z.string(),
    }),
  ),
});
const attempt = z.object({
  id: z.string(),
  quizRevision: z.number().int(),
  answers: z.array(z.number().int()),
  score: z.number().int(),
  total: z.number().int(),
  passed: z.boolean(),
  submittedAt: z.string(),
  feedback: z.array(
    z.object({
      questionId: z.string(),
      correct: z.boolean(),
      explanation: z.string(),
    }),
  ),
});

class QuizTransport {
  constructor(private readonly transport: HttpTransport) {}
  async request(
    path: string,
    method = "GET",
    body?: unknown,
  ): Promise<unknown> {
    const response = await this.transport(path, {
      method,
      credentials: "same-origin",
      signal: AbortSignal.timeout(240000),
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data: unknown = await response.json();
    if (!response.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? data.detail
          : null;
      throw new Error(
        typeof detail === "string"
          ? detail
          : "The quiz request failed. Please try again.",
      );
    }
    return data;
  }
}

export class HttpLessonQuizzes implements LessonQuizBackend {
  private readonly http: QuizTransport;
  constructor(transport: HttpTransport) {
    this.http = new QuizTransport(transport);
  }
  private path(id: string) {
    return `/api/v1/lessons/${encodeURIComponent(id)}/quiz`;
  }
  async get(id: string) {
    return authorQuiz.nullable().parse(await this.http.request(this.path(id)));
  }
  async save(request: Parameters<LessonQuizBackend["save"]>[0]) {
    return authorQuiz.parse(
      await this.http.request(this.path(request.lessonId), "PUT", {
        questions: request.questions,
        expectedRevision: request.expectedRevision,
      }),
    );
  }
  async generate(
    id: string,
    generationMode?: GenerationMode,
    onlyIfMissing = false,
  ) {
    return authorQuiz.parse(
      await this.http.request(this.path(id) + "/generate", "POST", {
        generationMode,
        onlyIfMissing,
      }),
    );
  }
}

export class HttpLearnerQuizzes implements LearnerQuizApplication {
  private readonly http: QuizTransport;
  constructor(transport: HttpTransport) {
    this.http = new QuizTransport(transport);
  }
  private path(id: string) {
    return `/api/v1/published/lessons/${encodeURIComponent(id)}/quiz`;
  }
  async get(id: string) {
    return learnerQuiz.nullable().parse(await this.http.request(this.path(id)));
  }
  async submit(id: string, quizRevision: number, answers: readonly number[]) {
    return attempt.parse(
      await this.http.request(this.path(id) + "/submit", "POST", {
        quizRevision,
        answers,
      }),
    );
  }
  async attempts(id: string) {
    return z
      .object({ items: z.array(attempt) })
      .parse(await this.http.request(this.path(id) + "/attempts")).items;
  }
}
