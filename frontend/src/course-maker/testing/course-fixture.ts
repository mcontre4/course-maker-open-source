import type { Course } from "../domain/course";

export function courseFixture(): Course {
  return {
    id: "course_test",
    title: "Test course",
    description: "A test learning goal",
    duration: { mode: "total", hours: 3 },
    image: "python",
    status: "draft",
    reviewed: [],
    completed: [],
    messages: [],
    chapters: [
      {
        id: "chapter_1",
        title: "Basics",
        summary: "Learn the basics",
        image: "python",
        lessons: [
          {
            id: "lesson_1",
            title: "First steps",
            topics: ["Variables", "Strings"],
            image: "variables",
            minutes: 45,
            videoUrl: "/test-media/lesson.mp4",
            quiz: [
              {
                id: "question_1",
                prompt: "First question",
                options: ["Yes", "No"],
                answer: 0,
                explanation: "Yes is correct.",
              },
            ],
          },
        ],
      },
    ],
  };
}
