import { quizFor } from "./quiz-generator";
import type { Chapter, CourseDetails } from "../../domain/course";
import { totalHours } from "../../domain/course";
import type {
  GeneratedSyllabus,
  SyllabusGenerator,
} from "../../application/ports";
import outline from "./outline.json";

const images = [
  "variables",
  "strings",
  "decisions",
  "loops",
  "lists1",
  "dict",
  "read",
  "write",
  "functions1",
  "parameters",
  "errors",
  "modules",
  "plan",
  "build1",
  "test",
  "personal",
];
const chapterImages = ["python", "lists", "functions", "build"];
const isPython = (details: CourseDetails) =>
  /python/i.test(details.title + " " + details.description);

export function buildDemoOutline(details: CourseDetails): readonly Chapter[] {
  const hours = totalHours(details.duration);
  const python = isPython(details);
  const source = python
    ? outline
    : [
        {
          title: "Build your foundation",
          summary:
            "Understand the essential concepts and set a clear learning goal.",
          lessons: [
            {
              title: `Getting started with ${details.title}`,
              topics: [
                "Define your starting point and learning goal",
                "Learn the essential vocabulary",
                "Explore a concrete beginner example",
                "Try your first guided exercise",
              ],
            },
          ],
        },
        {
          title: "Put ideas into practice",
          summary:
            "Explore the main techniques through small, focused exercises.",
          lessons: [
            {
              title: "Your first practical steps",
              topics: [
                "Break a task into smaller steps",
                "Follow a worked example",
                "Practice the core technique",
                "Reflect on what worked",
              ],
            },
          ],
        },
        {
          title: "Deepen your understanding",
          summary:
            "Connect concepts, recognize mistakes, and work more independently.",
          lessons: [
            {
              title: "Build confidence through practice",
              topics: [
                "Connect the concepts you have learned",
                "Identify common mistakes",
                "Try a slightly harder example",
                "Explain your approach in your own words",
              ],
            },
          ],
        },
        {
          title: "Make something of your own",
          summary: "Apply your learning in a small personal project.",
          lessons: [
            {
              title: "Your personal project",
              topics: [
                "Choose a project related to your learning goal",
                "Plan the steps and complete a first version",
                "Review and improve the result",
                "Decide what you want to learn next",
              ],
            },
          ],
        },
      ];
  const chapters = source.map((chapter, c) => ({
    ...chapter,
    lessons: hours < 6 ? chapter.lessons.slice(0, 1) : chapter.lessons,
  }));
  const count = chapters.reduce((n, c) => n + c.lessons.length, 0);
  const budget = Math.round(hours * 60);
  const minutes = Math.floor(budget / count);
  let position = 0;
  return chapters.map((chapter, c) => ({
    id: `chapter_${c + 1}`,
    title: chapter.title,
    summary: chapter.summary,
    image: python ? chapterImages[c] : ["plan", "build", "test", "personal"][c],
    lessons: chapter.lessons.map((lesson, l) => ({
      id: `lesson_${c * 4 + l + 1}`,
      title: lesson.title,
      image: python
        ? images[c * 4 + l]
        : ["plan", "build1", "test", "personal"][c],
      topics: lesson.topics,
      minutes: minutes + (position++ < budget % count ? 1 : 0),
      videoUrl: null,
      quiz: quizFor(lesson.title, lesson.topics),
    })),
  }));
}

export class DemoSyllabusGenerator implements SyllabusGenerator {
  async generate(details: CourseDetails): Promise<GeneratedSyllabus> {
    return {
      image: isPython(details) ? "python" : "story",
      chapters: buildDemoOutline(details),
    };
  }
}
