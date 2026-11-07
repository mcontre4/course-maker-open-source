import type {
  CancelGenerationRequest,
  GenerationCancellation,
} from "../../application/cancel-generation";
import type { HttpTransport } from "./course-backend";

export class HttpGenerationCancellation implements GenerationCancellation {
  constructor(private readonly transport: HttpTransport) {}

  async cancel(request: CancelGenerationRequest): Promise<boolean> {
    const resource = request.kind === "course" ? "courses" : "lessons";
    const response = await this.transport(
      `/api/v1/${resource}/${encodeURIComponent(request.id)}/generation/cancel`,
      {
        method: "POST",
        credentials: "same-origin",
        signal: AbortSignal.timeout(10000),
      },
    );
    if (!response.ok)
      throw new Error("Unable to cancel generation. Please try again.");
    const result: unknown = await response.json();
    return (
      !!result &&
      typeof result === "object" &&
      "cancelled" in result &&
      result.cancelled === true
    );
  }
}
