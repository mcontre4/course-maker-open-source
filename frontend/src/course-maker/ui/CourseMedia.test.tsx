import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import App from "../../App";
import { animatorModels } from "../application/animator-model";
import type { CourseMediaRequest } from "../application/media";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import { ApplicationContext } from "./application-context";
import { CourseMedia } from "./CourseMedia";

it("keeps the course preview player available while its final video is processing", async () => {
  const courses = new MemoryCourseBackend();
  const lesson = courses.value.chapters[0].lessons[0];
  courses.value = {
    ...courses.value,
    status: "ready",
    chapters: courses.value.chapters.map((chapter) => ({
      ...chapter,
      lessons: chapter.lessons.map((item) =>
        item.id === lesson.id
          ? {
              ...item,
              videoUrl: null,
              animation: {
                status: "animation_ready",
                projectKey: "saved/javascript",
                outputHash: "a".repeat(64),
                reviewStatus: "pending",
              },
            }
          : item,
      ),
    })),
  };
  render(
    <ApplicationContext.Provider
      value={createBackendCourseApplication(courses)}
    >
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter
          initialEntries={[`/courses/${courses.value.id}/lessons/${lesson.id}`]}
        >
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  expect(
    await screen.findByRole("button", { name: "Edit lesson" }),
  ).toBeVisible();
  expect(screen.getByLabelText(`${lesson.title} video`)).toHaveAttribute(
    "src",
    `/api/v1/courses/${courses.value.id}/lessons/${lesson.id}/video?v=${"a".repeat(64)}`,
  );
});

it.each([undefined, ...animatorModels.map((model) => model.id)])(
  "sends animator choice %s from the course studio when generating video",
  async (animatorModel) => {
    const courses = new MemoryCourseBackend();
    const lessons = new MemoryStandaloneBackend();
    const draft = await lessons.create({
      title: "Atoms",
      description: "Explain atoms",
      minutes: 1,
    });
    const planned = await lessons.plan({
      id: draft.id,
      expectedRevision: 0,
      message: "Plan",
    });
    const requests: CourseMediaRequest[] = [];
    const app = {
      ...createBackendCourseApplication(courses),
      generateMedia: {
        execute: async (request: CourseMediaRequest) => {
          requests.push(request);
          return courses.value;
        },
      },
    };
    render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={new QueryClient()}>
          <CourseMedia
            course={courses.value}
            lesson={planned.content}
            mode="fast"
          />
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    const user = userEvent.setup();
    if (animatorModel) {
      await user.selectOptions(
        screen.getByRole("combobox", { name: "Animator model" }),
        animatorModel,
      );
    }
    const toggle = screen.getByLabelText("Pre-generate visual elements");
    expect(toggle).not.toBeChecked();
    if (animatorModel) await user.click(toggle);
    expect(
      screen.queryByRole("combobox", { name: "Animation and review engine" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Generate lesson video →" }),
    );
    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0]).toEqual({
      courseId: courses.value.id,
      lessonId: planned.id,
      stage: "video",
      animationBackend: "direct",
      generationMode: "fast",
      ...(animatorModel ? { animatorModel, prepareElements: true } : {}),
    });
  },
);
