import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { createBackendCourseApplication } from "../composition";
import type { CancelGenerationRequest } from "../application/cancel-generation";
import { MemoryCourseBackend } from "../testing/course-backend";
import { ApplicationContext } from "./application-context";
import { CancelGenerationButton } from "./CancelGenerationButton";

it.each(["script", "video"])(
  "cancels %s generation and keeps cancellation pending until the worker stops",
  async (label) => {
    const requests: CancelGenerationRequest[] = [];
    const app = {
      ...createBackendCourseApplication(new MemoryCourseBackend()),
      cancelGeneration: {
        execute: async (request: CancelGenerationRequest) => {
          requests.push(request);
          return true;
        },
      },
    };
    const cache = new QueryClient();
    const view = (pending: boolean) => (
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={cache}>
          <CancelGenerationButton
            kind="lesson"
            id="lesson_one"
            pending={pending}
            label={`${label} generation`}
          />
        </QueryClientProvider>
      </ApplicationContext.Provider>
    );
    const rendered = render(view(true));
    await userEvent
      .setup()
      .click(
        screen.getByRole("button", { name: `Cancel ${label} generation` }),
      );
    expect(
      await screen.findByRole("button", { name: "Cancellation requested" }),
    ).toBeDisabled();
    expect(requests).toEqual([{ kind: "lesson", id: "lesson_one" }]);
    expect(screen.getByRole("status")).toHaveTextContent(
      "completed stages are saved",
    );
    rendered.rerender(view(false));
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    rendered.rerender(view(true));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: `Cancel ${label} generation` }),
      ).toBeEnabled(),
    );
  },
);

it("restores cancellation requested by another tab", () => {
  const app = {
    ...createBackendCourseApplication(new MemoryCourseBackend()),
    cancelGeneration: { execute: async () => true },
  };
  render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider client={new QueryClient()}>
        <CancelGenerationButton
          kind="course"
          id="course_one"
          pending
          operation="cancelling/video"
        />
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  expect(
    screen.getByRole("button", { name: "Cancellation requested" }),
  ).toBeDisabled();
});

it("offers a retry when cancelling fails", async () => {
  const app = {
    ...createBackendCourseApplication(new MemoryCourseBackend()),
    cancelGeneration: {
      execute: async () => {
        throw new Error("Connection failed");
      },
    },
  };
  render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { mutations: { retry: false } } })
        }
      >
        <CancelGenerationButton kind="lesson" id="lesson_one" pending />
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Cancel generation" }));
  expect(await screen.findByText("Connection failed")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Cancel generation" }),
  ).toBeEnabled();
});
