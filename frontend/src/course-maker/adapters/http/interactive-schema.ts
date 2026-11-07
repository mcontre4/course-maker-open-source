import { z } from "zod";

export const interactiveSchema = z.object({
  planHash: z.string(),
  reason: z.string(),
  spec: z
    .object({
      kind: z.enum(["pendulum", "custom"]),
      title: z.string(),
      objective: z.string(),
      explanation: z.string(),
      controls: z.array(z.string()),
      behavior: z.string(),
      prompts: z.array(z.string()),
      acceptanceCriteria: z.array(z.string()),
      initialLength: z.number(),
      initialGravity: z.number(),
      initialAngle: z.number(),
    })
    .nullable(),
  html: z.string().nullable(),
});
