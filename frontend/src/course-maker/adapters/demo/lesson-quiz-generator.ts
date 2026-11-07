import type { LessonResponse } from "../../application/dto";
import type { LessonQuizGenerator } from "../../application/lesson-quizzes";
import { LessonQuizError, type QuizQuestion } from "../../domain/lesson-quiz";

const fillers = [
  "None of these describes this lesson",
  "This is not covered in the lesson",
  "It depends on details the lesson never mentions",
];

/**
 * Offline drafting from the lesson outline: each teaching beat's check
 * question becomes a question, with answers borrowed from the rest of the plan.
 */
export class OutlineQuizGenerator implements LessonQuizGenerator {
  async generate(lesson: LessonResponse): Promise<readonly QuizQuestion[]> {
    const plan = lesson.plan;
    const beats = (plan?.beats ?? []).filter(
      (beat) => beat.checkQuestion.trim() && beat.expectedAnswer.trim(),
    );
    if (!plan || !beats.length)
      throw new LessonQuizError(
        "Create the lesson outline first — questions are drafted from it.",
      );
    return beats.slice(0, 8).map((beat, index) => {
      const correct = beat.expectedAnswer.trim();
      const pool = [
        ...plan.misconceptions,
        ...beats.filter((other) => other !== beat).map((o) => o.expectedAnswer),
        ...plan.scopeBoundaries,
        ...fillers,
      ]
        .map((text) => text.trim())
        .filter(
          (text, at, all) =>
            text &&
            text.toLowerCase() !== correct.toLowerCase() &&
            all.findIndex((x) => x.toLowerCase() === text.toLowerCase()) === at,
        );
      const options = pool.slice(0, 3);
      // Spread the right answer around so it is not always first.
      const correctIndex = index % (options.length + 1);
      options.splice(correctIndex, 0, correct);
      return {
        id: `question_${index + 1}`,
        kind: "multiple_choice",
        prompt: beat.checkQuestion.trim(),
        options,
        correctIndex,
        explanation: beat.purpose.trim()
          ? `${beat.title}: ${beat.purpose.trim()}`
          : beat.title,
      } satisfies QuizQuestion;
    });
  }
}
