import { expect, it } from "vitest";
import { lessonPlaybackUrl } from "./lesson-view";
import type { LessonResponse } from "../../application/dto";

it("changes playback identity when the render changes within the same project", () => {
  const lesson: LessonResponse = {
    id: "lesson_one",
    title: "Running mechanics",
    topics: ["Running"],
    minutes: 1,
    image: "",
    videoUrl: null,
    quiz: [],
    animation: {
      status: "animation_ready",
      projectKey: "saved/remotion",
      outputHash: "first-render",
    },
  };
  const previous = lessonPlaybackUrl(lesson);
  const current = lessonPlaybackUrl({
    ...lesson,
    animation: { ...lesson.animation!, outputHash: "new-render" },
  });
  expect(previous).toBe("/api/v1/lessons/lesson_one/video?v=first-render");
  expect(current).toBe("/api/v1/lessons/lesson_one/video?v=new-render");
  expect(
    lessonPlaybackUrl({ ...lesson, videoUrl: "https://example.com/video.mp4" }),
  ).toBe("https://example.com/video.mp4");
});
