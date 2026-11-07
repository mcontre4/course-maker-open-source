import { describe, expect, it } from "vitest";
import { HttpCourseMedia } from "./media";
import { HttpCourseBackend, type HttpTransport } from "./course-backend";

describe("course media HTTP contracts", () => {
  it.each(["storyboard", "speech", "animation", "video"] as const)(
    "sends only supported fields for %s",
    async (stage) => {
      const writes: { url: string; body: unknown }[] = [];
      const transport: HttpTransport = async (url, init) => {
        let data: unknown = {};
        if (init?.method === "POST")
          writes.push({ url, body: JSON.parse(String(init.body)) });
        else if (url.endsWith("/syllabus/session"))
          data = { revision: 1, turns: [], curriculum: null };
        else if (url.endsWith("/spend"))
          return new Response("{}", { status: 503 });
        else
          data = {
            id: "course_one",
            title: "Science",
            description: "Learn science",
            duration: { mode: "total", hours: 1 },
            image: "",
            status: "ready",
            chapters: [],
            reviewed: [],
            completed: [],
          };
        return new Response(JSON.stringify(data), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };
      const media = new HttpCourseMedia(
        transport,
        new HttpCourseBackend(transport),
      );
      await media.advance({
        courseId: "course_one",
        lessonId: "lesson_one",
        stage,
        generationMode: "fast",
        animatorModel: "anthropic/claude-opus-5.5",
        prepareElements: true,
        animationBackend: "direct",
      });
      expect(writes[0].body).toEqual(
        stage === "speech"
          ? { lessonId: "lesson_one" }
          : {
              lessonId: "lesson_one",
              generationMode: "fast",
              ...(["animation", "video"].includes(stage)
                ? {
                    animatorModel: "anthropic/claude-opus-5.5",
                    prepareElements: true,
                    animationBackend: "direct",
                  }
                : {}),
              ...(stage === "animation"
                ? { visualStyle: "Follow the saved course and lesson style." }
                : {}),
            },
      );
      expect(writes[0].url).toContain(
        {
          video: "/video/generate",
          storyboard: "/storyboards/generate",
          speech: "/speech/generate",
          animation: "/animations/generate",
        }[stage],
      );
    },
  );
});
