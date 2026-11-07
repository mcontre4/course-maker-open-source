import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LessonPlayer } from "./LessonPlayer";
import type { LessonResponse } from "../../application/dto";

const lesson: LessonResponse = {
  id: "lesson_video",
  title: "Working with lists",
  image: "lists1",
  topics: ["Create a list"],
  minutes: 20,
  videoUrl: "/test-media/lesson.mp4",
  quiz: [],
};
describe("video lesson playback", () => {
  it("uses native controls and records completion only when playback ends", () => {
    let completions = 0;
    render(
      <LessonPlayer
        lesson={lesson}
        courseTitle="Python"
        watched={false}
        pending={false}
        onWatched={() => {
          completions += 1;
        }}
      />,
    );
    const video = screen.getByLabelText("Working with lists video");
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("src", "/test-media/lesson.mp4");
    fireEvent.play(video);
    fireEvent.pause(video);
    expect(completions).toBe(0);
    fireEvent.ended(video);
    expect(completions).toBe(1);
  });
  it("offers a retry when the video cannot load", async () => {
    const user = userEvent.setup();
    render(
      <LessonPlayer
        lesson={lesson}
        courseTitle="Python"
        watched={false}
        pending={false}
        onWatched={() => {}}
      />,
    );
    const previous = screen.getByLabelText("Working with lists video");
    fireEvent.error(previous);
    expect(screen.getByRole("alert")).toHaveTextContent("couldn’t be loaded");
    await user.click(screen.getByRole("button", { name: "Retry video" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Working with lists video")).not.toBe(
      previous,
    );
  });
});
