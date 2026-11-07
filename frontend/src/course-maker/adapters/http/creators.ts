import { z } from "zod";
import type { Creators } from "../../application/creators";
import type { HttpTransport } from "./course-backend";

const creator = z.object({
  id: z.string(),
  name: z.string(),
  picture: z.string().nullable(),
});
const lesson = z.object({
  id: z.string(),
  title: z.string(),
  minutes: z.number(),
  image: z.string(),
  videoUrl: z.string().nullable(),
  courseId: z.string().nullable(),
});
const page = z.object({
  creator,
  lessons: z.array(lesson),
  courses: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      description: z.string(),
      image: z.string(),
      lessons: z.array(lesson),
    }),
  ),
});
export class HttpCreators implements Creators {
  constructor(private readonly transport: HttpTransport) {}
  private async read<T>(
    schema: z.ZodType<T>,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await this.transport("/api/v1" + path, {
      method: body ? "PUT" : "GET",
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok)
      throw new Error(
        response.status === 404
          ? "This creator or published lesson could not be found."
          : "Couldn’t load creator details. Please try again.",
      );
    return schema.parse(await response.json());
  }
  discover(query?: string) {
    const params = query?.trim()
      ? "?" + new URLSearchParams({ q: query.trim(), limit: "50" })
      : "";
    return this.read(
      page.omit({ creator: true }),
      "/published/discovery" + params,
    );
  }
  own() {
    return this.read(creator, "/creators/me");
  }
  save(profile: { name: string; picture: string | null }) {
    return this.read(creator, "/creators/me", profile);
  }
  page(id: string) {
    return this.read(page, "/creators/" + encodeURIComponent(id));
  }
  watch(id: string, courseId?: string) {
    return this.read(
      z.object({ creator: creator.nullable(), lesson }),
      "/published/lessons/" +
        encodeURIComponent(id) +
        (courseId ? "?course_id=" + encodeURIComponent(courseId) : ""),
    );
  }
}
