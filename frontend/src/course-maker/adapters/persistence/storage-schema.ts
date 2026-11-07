import { z } from "zod";

const question = z.object({
  id: z.string(),
  prompt: z.string(),
  options: z.array(z.string()).min(2),
  answer: z.number().int().nonnegative(),
  explanation: z.string(),
});
const lesson = z.object({
  id: z.string(),
  title: z.string(),
  image: z.string(),
  topics: z.array(z.string()).min(1),
  minutes: z.number().positive(),
  videoUrl: z.string().nullable(),
  quiz: z.array(question).min(1),
});
const course = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  image: z.string(),
  duration: z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("total"), hours: z.number() }),
    z.object({
      mode: z.literal("weekly"),
      weeks: z.number(),
      hoursPerWeek: z.number(),
    }),
  ]),
  status: z.enum(["draft", "ready"]),
  chapters: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      summary: z.string(),
      image: z.string(),
      lessons: z.array(lesson).min(1),
    }),
  ),
  reviewed: z.array(z.string()),
  completed: z.array(z.string()),
  messages: z.array(
    z.object({ role: z.enum(["guide", "learner"]), text: z.string() }),
  ),
});
export const persisted = z.object({
  version: z.literal(1),
  courses: z.array(course),
});
