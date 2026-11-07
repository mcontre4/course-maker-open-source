import { it, expect } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { LessonResponse } from "../../application/dto";
import { LiveLessonPlayer } from "./LiveLessonPlayer";

const lesson: LessonResponse = {
  id: "lesson_one",
  title: "Moon phases",
  topics: ["Moon"],
  minutes: 1,
  image: "",
  quiz: [],
  videoUrl: "/api/v1/lessons/lesson_one/video",
  animation: {
    status: "animation_ready",
    projectKey: "a".repeat(64) + "/javascript",
    reviewStatus: "pending",
  },
};

function fixture() {
  let ready = false;
  let error = false;
  let checks = 0;
  const playback = {
    async execute() {
      checks++;
      if (error) throw new Error("Offline");
      return {
        sourceHash: "b".repeat(64),
        videoReady: ready,
        previewUrl: "/api/v1/lessons/lesson_one/preview?v=" + "b".repeat(64),
        videoUrl: "/api/v1/lessons/lesson_one/video?v=" + "b".repeat(64),
      };
    },
  };
  return {
    playback,
    finish: () => {
      ready = true;
    },
    fail: () => {
      error = true;
    },
    recover: () => {
      error = false;
    },
    checks: () => checks,
  };
}

function message(frame: HTMLIFrameElement, type: string, time = 0) {
  act(() =>
    window.dispatchEvent(
      new MessageEvent("message", {
        source: frame.contentWindow,
        data: { channel: "lesson-preview", type, time },
      }),
    ),
  );
}

it("keeps code playing after delivery completes and chooses MP4 on the next play", async () => {
  const f = fixture();
  const props = { lesson, courseTitle: "Astronomy", playback: f.playback };
  const { container, rerender } = render(<LiveLessonPlayer {...props} />);
  const frame = (await screen.findByTitle(
    "Moon phases live preview",
  )) as HTMLIFrameElement;
  message(frame, "ready");
  expect(container.querySelector("video")).toBeNull();
  message(frame, "play-request", 4);
  await waitFor(() => expect(f.checks()).toBe(2));
  f.finish();
  rerender(
    <LiveLessonPlayer
      {...props}
      lesson={{
        ...lesson,
        animation: { ...lesson.animation!, reviewStatus: "skipped" },
      }}
    />,
  );
  expect(container.querySelector("iframe")).toBe(frame);
  expect(container.querySelector("video")).toBeNull();
  expect(f.checks()).toBe(2);
  message(frame, "play-request", 8);
  await waitFor(() => expect(container.querySelector("video")).not.toBeNull());
  expect(container.querySelector("video")).toHaveAttribute(
    "src",
    expect.stringContaining("/video?v="),
  );
  expect(container.querySelector("iframe")).toBeNull();
});

it("uses MP4 immediately when reopening a completed lesson", async () => {
  const f = fixture();
  f.finish();
  const { container } = render(
    <LiveLessonPlayer
      lesson={lesson}
      courseTitle="Astronomy"
      playback={f.playback}
    />,
  );
  await waitFor(() => expect(container.querySelector("video")).not.toBeNull());
  expect(container.querySelector("iframe")).toBeNull();
});

it("keeps the active preview mounted when polling publishes repaired code", async () => {
  const f = fixture();
  const { rerender } = render(
    <LiveLessonPlayer
      lesson={lesson}
      courseTitle="Astronomy"
      playback={f.playback}
    />,
  );
  const frame = (await screen.findByTitle(
    "Moon phases live preview",
  )) as HTMLIFrameElement;
  message(frame, "ready");
  rerender(
    <LiveLessonPlayer
      lesson={{
        ...lesson,
        animation: { ...lesson.animation!, outputHash: "repaired" },
      }}
      courseTitle="Astronomy"
      playback={f.playback}
    />,
  );
  expect(screen.getByTitle("Moon phases live preview")).toBe(frame);
  expect(f.checks()).toBe(1);
  message(frame, "play-request", 8);
  await waitFor(() => expect(f.checks()).toBe(2));
});

it("accepts its own completion and records progress while rendering continues", async () => {
  const f = fixture();
  let watched = 0;
  const onWatched = () => {
    watched++;
  };
  const { rerender } = render(
    <LiveLessonPlayer
      lesson={lesson}
      courseTitle="Astronomy"
      playback={f.playback}
      onWatched={onWatched}
    />,
  );
  const frame = (await screen.findByTitle(
    "Moon phases live preview",
  )) as HTMLIFrameElement;
  act(() =>
    window.dispatchEvent(
      new MessageEvent("message", {
        source: window,
        data: { channel: "lesson-preview", type: "ended" },
      }),
    ),
  );
  expect(watched).toBe(0);
  message(frame, "ended");
  await waitFor(() => expect(watched).toBe(1));
  rerender(
    <LiveLessonPlayer
      lesson={{
        ...lesson,
        animation: { ...lesson.animation!, reviewStatus: "skipped" },
      }}
      courseTitle="Astronomy"
      playback={f.playback}
      onWatched={onWatched}
    />,
  );
  await waitFor(() => expect(watched).toBe(1));
  message(frame, "ended");
  expect(watched).toBe(1);
});

it("offers retry when the availability check fails", async () => {
  const f = fixture();
  f.fail();
  render(
    <LiveLessonPlayer
      lesson={lesson}
      courseTitle="Astronomy"
      playback={f.playback}
    />,
  );
  await screen.findByRole("alert");
  f.recover();
  fireEvent.click(screen.getByRole("button", { name: "Retry playback" }));
  await screen.findByTitle("Moon phases live preview");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("selects playback again when navigating to another lesson", async () => {
  const playback = {
    async execute({ lessonId }: { lessonId: string }) {
      return {
        sourceHash: lessonId,
        videoReady: false,
        previewUrl: `/preview/${lessonId}`,
        videoUrl: `/video/${lessonId}`,
      };
    },
  };
  const { rerender } = render(
    <LiveLessonPlayer
      lesson={lesson}
      courseTitle="Astronomy"
      playback={playback}
    />,
  );
  await waitFor(() =>
    expect(screen.getByTitle("Moon phases live preview")).toHaveAttribute(
      "src",
      "/preview/lesson_one",
    ),
  );
  rerender(
    <LiveLessonPlayer
      lesson={{ ...lesson, id: "lesson_two" }}
      courseTitle="Astronomy"
      playback={playback}
    />,
  );
  await waitFor(() =>
    expect(screen.getByTitle("Moon phases live preview")).toHaveAttribute(
      "src",
      "/preview/lesson_two",
    ),
  );
});
