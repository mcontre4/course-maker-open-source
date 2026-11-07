import type { QuizGenerator } from "../../application/ports";
import type { Lesson, Question } from "../../domain/course";

export function quizFor(
  title: string,
  topics: readonly string[],
): readonly Question[] {
  if (
    title.includes("lists") &&
    topics.some((t) => t.includes("append")) &&
    topics.some((t) => t.includes("index")) &&
    topics.some((t) => t.includes("Loop"))
  )
    return [
      {
        id: "question_1",
        prompt: "Which line adds “learn” to the end of a list?",
        options: [
          'plans.append("learn")',
          'plans.remove("learn")',
          'plans[0] = "learn"',
        ],
        answer: 0,
        explanation: "append() adds one item to the end of a list.",
      },
      {
        id: "question_2",
        prompt: "What is the index of the first item in a Python list?",
        options: ["1", "0", "−1"],
        answer: 1,
        explanation:
          "Python list indexes start at zero. An index of −1 refers to the last item.",
      },
      {
        id: "question_3",
        prompt: "How can you process every item in a list?",
        options: [
          "Print only its name",
          "Replace the list with a string",
          "Use a for loop",
        ],
        answer: 2,
        explanation: "A for loop visits each item in the list in order.",
      },
    ];
  return [
    {
      id: "question_1",
      prompt: "Which task is part of this lesson?",
      options: [
        topics[0],
        "Skip the examples and memorize the title",
        "Ignore the learning goal",
      ],
      answer: 0,
      explanation: `This lesson focuses on: ${topics[0]}.`,
    },
    {
      id: "question_2",
      prompt: "What should you practice after the explanation?",
      options: [
        "Move on without trying it",
        topics[1] ?? topics[0],
        "Only copy the lesson heading",
      ],
      answer: 1,
      explanation: `Try it yourself: ${topics[1] ?? topics[0]}.`,
    },
    {
      id: "question_3",
      prompt: "How can you check your understanding?",
      options: [
        "Avoid mistakes by never practicing",
        "Read the title again",
        "Try a small example, explain the result, and check it",
      ],
      answer: 2,
      explanation:
        "Applying a concept and explaining the result makes gaps in understanding visible.",
    },
  ];
}

export class DemoQuizGenerator implements QuizGenerator {
  async generate(lesson: Lesson): Promise<readonly Question[]> {
    return quizFor(lesson.title, lesson.topics);
  }
}
