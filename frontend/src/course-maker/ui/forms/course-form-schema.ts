import { z } from "zod";

export const schema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("total"),
    title: z.string().trim().min(1, "Give your course a title.").max(120),
    description: z
      .string()
      .refine(
        (value) => value.trim().length > 0,
        "Tell us what you want to learn.",
      )
      .max(2000),
    hours: z.number().min(1).max(480, "The maximum is 480 hours."),
  }),
  z.object({
    mode: z.literal("weekly"),
    title: z.string().trim().min(1, "Give your course a title.").max(120),
    description: z
      .string()
      .refine(
        (value) => value.trim().length > 0,
        "Tell us what you want to learn.",
      )
      .max(2000),
    weeks: z.number().int().min(1).max(12, "Choose up to 12 weeks."),
    hoursPerWeek: z.number().min(1).max(40, "Choose up to 40 hours per week."),
  }),
]);
export type FormValues = z.infer<typeof schema>;
