import { z } from "zod";
import type { LearningActivityLog } from "../../application/learning-activity";
import type { HttpTransport } from "./course-backend";

const activity = z.object({
  items: z.array(z.object({ itemId: z.string(), lastOpenedAt: z.string() })),
});
export class HttpLearningActivity implements LearningActivityLog {
  constructor(private readonly transport: HttpTransport) {}
  async recent() {
    const response = await this.transport("/api/v1/learning-activity", {
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("Couldn’t load your recent activity.");
    return activity.parse(await response.json()).items;
  }
  async record(itemId: string) {
    const response = await this.transport(
      "/api/v1/learning-activity/" + encodeURIComponent(itemId),
      { method: "PUT", credentials: "same-origin" },
    );
    if (!response.ok) throw new Error("Couldn’t save your recent activity.");
  }
}
