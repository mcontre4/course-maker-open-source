import type { Course, CourseDetails } from "../../domain/course";
import { buildDemoOutline } from "./syllabus-generator";

export function createDemoCourses(): readonly Course[] {
  const details: CourseDetails = {
    title: "Python for everyday life",
    description: "Build useful little programs, one lesson at a time.",
    duration: { mode: "weekly", weeks: 4, hoursPerWeek: 3 },
  };
  const story: CourseDetails = {
    title: "The art of telling a good story",
    description: "Learn to turn a simple idea into an engaging short story.",
    duration: { mode: "total", hours: 3 },
  };
  const base = {
    reviewed: [],
    completed: [],
    messages: [
      {
        role: "guide" as const,
        text: "Review each lesson’s coverage. Use the topic controls to make this plan yours before approving it.",
      },
    ],
  };
  return [
    {
      ...base,
      ...details,
      id: "course_python_demo",
      image: "python",
      status: "ready",
      chapters: buildDemoOutline(details),
      reviewed: ["lesson_1", "lesson_2", "lesson_3", "lesson_4"],
      completed: ["lesson_1", "lesson_2", "lesson_3", "lesson_4"],
    },
    {
      ...base,
      ...story,
      id: "course_story_demo",
      image: "story",
      status: "draft",
      chapters: buildDemoOutline(story),
    },
  ];
}
