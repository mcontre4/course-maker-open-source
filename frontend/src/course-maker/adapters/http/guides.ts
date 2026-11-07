import { z } from "zod";
import type { Guides, GuideRole, GuideMemory } from "../../application/guides";
import type { HttpTransport } from "./course-backend";

const turn = z.object({
  id: z.string(),
  revision: z.number(),
  user: z.string(),
  assistant: z.string(),
});
const chat = z
  .object({
    id: z.string(),
    resource_id: z.string(),
    guide: z.enum(["lesson", "syllabus", "storyboard", "animation"]),
    title: z.string(),
    revision: z.number(),
    turns: z.array(turn),
    has_more: z.boolean(),
  })
  .transform((value) => ({
    ...value,
    resourceId: value.resource_id,
    hasMore: value.has_more,
  }));
const memory = z
  .object({
    id: z.string(),
    scope: z.enum(["user", "lesson"]),
    key: z.string(),
    content: z.string(),
    source_message_id: z.string(),
    revision: z.number(),
  })
  .transform((value) => ({
    ...value,
    sourceMessageId: value.source_message_id,
  }));
const version = z
  .object({
    revision: z.number(),
    outline_json: z.string(),
    description: z.string(),
    source_message_id: z.string(),
    created_at: z.string(),
  })
  .transform((value) => ({
    ...value,
    outlineJson: value.outline_json,
    sourceMessageId: value.source_message_id,
    createdAt: value.created_at,
  }));

export class HttpGuides implements Guides {
  constructor(private readonly transport: HttpTransport) {}

  private async request(
    path: string,
    body?: unknown,
    method?: string,
  ): Promise<unknown> {
    let response: Response;
    try {
      response = await this.transport("/api/v1/guides" + path, {
        method: method ?? (body === undefined ? "GET" : "POST"),
        credentials: "same-origin",
        headers:
          body === undefined
            ? undefined
            : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(1200000),
      });
    } catch {
      throw new Error(
        "Connection interrupted. Retry your message to check its saved result.",
      );
    }
    let value: unknown;
    try {
      value = await response.json();
    } catch {
      throw Object.assign(
        new Error(
          response.ok
            ? "Your guide returned an unreadable response. Please try again."
            : "Your guide is temporarily unavailable. Please try again.",
        ),
        { status: response.status },
      );
    }
    if (!response.ok) {
      const error = z.object({ detail: z.string() }).safeParse(value);
      throw Object.assign(
        new Error(error.success ? error.data.detail : "Guide request failed."),
        { status: response.status },
      );
    }
    return value;
  }
  async list(resourceId: string, guide: GuideRole) {
    return z
      .object({ items: z.array(chat) })
      .parse(
        await this.request(
          "/chats?" + new URLSearchParams({ resource_id: resourceId, guide }),
        ),
      ).items;
  }
  async create(resourceId: string, guide: GuideRole, title: string) {
    return chat.parse(
      await this.request("/chats", { resourceId, guide, title }),
    );
  }
  async get(id: string, before?: number) {
    return chat.parse(
      await this.request(
        "/chats/" +
          encodeURIComponent(id) +
          (before === undefined ? "" : "?before=" + before),
      ),
    );
  }
  async send(request: Parameters<Guides["send"]>[0]) {
    return chat.parse(
      await this.request(
        `/chats/${encodeURIComponent(request.threadId)}/messages`,
        {
          message: request.message,
          requestId: request.requestId,
          expectedRevision: request.expectedRevision,
          generationMode: request.generationMode,
        },
      ),
    );
  }
  async memories(resourceId: string) {
    return z
      .object({ items: z.array(memory) })
      .parse(
        await this.request(
          "/memories?" + new URLSearchParams({ resource_id: resourceId }),
        ),
      ).items;
  }
  async changeMemory(
    resourceId: string,
    item: GuideMemory,
    content: string | null,
  ) {
    const path = "/memories/" + encodeURIComponent(item.id);
    if (content === null) {
      await this.request(
        path +
          "?" +
          new URLSearchParams({
            resource_id: resourceId,
            expected_revision: String(item.revision),
          }),
        undefined,
        "DELETE",
      );
    } else {
      await this.request(
        path,
        { resourceId, content, expectedRevision: item.revision },
        "PUT",
      );
    }
  }
  async versions(resourceId: string, before?: number) {
    const query = new URLSearchParams({ resource_id: resourceId });
    if (before !== undefined) query.set("before", String(before));
    return z
      .object({ items: z.array(version) })
      .parse(await this.request("/outline-versions?" + query)).items;
  }
}
