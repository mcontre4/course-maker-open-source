/** Question kinds are a union so new formats can be added without reshaping quizzes. */
export type QuizQuestion = Readonly<{
  id: string;
  kind: "multiple_choice";
  prompt: string;
  options: readonly string[];
  correctIndex: number;
  explanation: string;
}>;

export type LessonQuiz = Readonly<{
  lessonId: string;
  questions: readonly QuizQuestion[];
  /** Whether the questions are still the generated draft or were changed by their creator. */
  origin: "generated" | "edited";
  revision?: number;
}>;

export const quizLimits = {
  questions: 20,
  minOptions: 2,
  maxOptions: 6,
  prompt: 500,
  option: 300,
  explanation: 800,
} as const;

/** The first problem with a question, in words a creator can act on, or null. */
export function questionProblem(question: QuizQuestion): string | null {
  const prompt = question.prompt.trim();
  const options = question.options.map((option) => option.trim());
  if (!prompt) return "Write the question.";
  if (prompt.length > quizLimits.prompt)
    return `Keep the question under ${quizLimits.prompt} characters.`;
  if (
    options.length < quizLimits.minOptions ||
    options.length > quizLimits.maxOptions
  )
    return `Use between ${quizLimits.minOptions} and ${quizLimits.maxOptions} answers.`;
  if (options.some((option) => !option))
    return "Fill in or remove empty answers.";
  if (options.some((option) => option.length > quizLimits.option))
    return `Keep each answer under ${quizLimits.option} characters.`;
  if (
    new Set(options.map((option) => option.toLowerCase())).size !==
    options.length
  )
    return "Each answer needs to be different.";
  if (
    !Number.isInteger(question.correctIndex) ||
    question.correctIndex < 0 ||
    question.correctIndex >= options.length
  )
    return "Choose the correct answer.";
  if (question.explanation.length > quizLimits.explanation)
    return `Keep the explanation under ${quizLimits.explanation} characters.`;
  return null;
}

/** The first problem with a set of questions, or null when it can be saved. */
export function quizProblem(questions: readonly QuizQuestion[]): string | null {
  if (!questions.length) return "Add at least one question.";
  if (questions.length > quizLimits.questions)
    return `A quiz can have up to ${quizLimits.questions} questions.`;
  for (const [index, question] of questions.entries()) {
    const problem = questionProblem(question);
    if (problem) return `Question ${index + 1}: ${problem}`;
  }
  return null;
}

export function blankQuestion(
  questions: readonly QuizQuestion[],
): QuizQuestion {
  const used = questions
    .map((question) => Number(/^question_(\d+)$/.exec(question.id)?.[1] ?? 0))
    .reduce((a, b) => Math.max(a, b), 0);
  return {
    id: `question_${used + 1}`,
    kind: "multiple_choice",
    prompt: "",
    options: ["", ""],
    correctIndex: 0,
    explanation: "",
  };
}

/** Trim text and drop nothing else, so what is saved is what was validated. */
export function tidyQuestions(
  questions: readonly QuizQuestion[],
): readonly QuizQuestion[] {
  return questions.map((question) => ({
    ...question,
    prompt: question.prompt.trim(),
    options: question.options.map((option) => option.trim()),
    explanation: question.explanation.trim(),
  }));
}

export class LessonQuizError extends Error {}
