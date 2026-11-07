import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import {
  AdvanceStandaloneLesson,
  CopyLesson,
  CreateStandaloneLesson,
  GetStandaloneLesson,
  ListStandaloneLessons,
  PlanStandaloneLesson,
} from "../application/standalone-lessons";
import { ApplicationContext } from "./application-context";
import { CopyLessonButton } from "./CopyLessonButton";
import { suggestCopyTitle } from "./CopyLessonDialog";

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

async function mount(image = "") {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Chemical bonds",
    description: "Explain bonding",
    minutes: 3,
    style: {
      visualStyleId: "flat-vector-science",
      description: "Flat vector science",
      audience: "Beginners",
      voiceId: "voice_one",
    },
  });
  const app = {
    ...createBackendCourseApplication(new MemoryCourseBackend()),
    lessons: {
      copy: new CopyLesson(backend),
      list: new ListStandaloneLessons(backend),
      get: new GetStandaloneLesson(backend),
      create: new CreateStandaloneLesson(backend),
      plan: new PlanStandaloneLesson(backend),
      advance: new AdvanceStandaloneLesson(backend),
    },
  };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/lessons/lesson_one"]}>
          <Routes>
            <Route
              path="/lessons/:id"
              element={
                <>
                  <CopyLessonButton
                    lessonId="lesson_one"
                    title="Chemical bonds"
                    image={image}
                  />
                  <Where />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  return { backend, user: userEvent.setup() };
}

describe("copy lesson sheet", () => {
  it("suggests the same name the server would give an untitled copy", () => {
    expect(suggestCopyTitle("Rain")).toBe("Rain-copy");
    expect(suggestCopyTitle("A".repeat(120))).toHaveLength(120);
  });

  it("opens with the suggested title selected and copies nothing until confirmed", async () => {
    const { backend, user } = await mount();
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    const dialog = screen.getByRole("dialog", { name: "Copy this lesson" });
    const title = within(dialog).getByLabelText("Title");
    expect(title).toHaveValue("Chemical bonds-copy");
    expect(title).toHaveFocus();
    expect(backend.copied).toEqual([]);
  });

  it("sends the edited title and opens the copy once it exists", async () => {
    const { backend, user } = await mount("flat-vector");
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText(/The thumbnail comes with it/),
    ).toBeVisible();
    const title = within(dialog).getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "  Bonds for my class  ");
    await user.click(
      within(dialog).getByRole("button", { name: "Create copy" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent(
        "/lessons/lesson_copy?step=review",
      ),
    );
    expect(backend.copied).toEqual([
      { id: "lesson_one", courseId: undefined, title: "Bonds for my class" },
    ]);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("says when there is no thumbnail to bring along", async () => {
    const { user } = await mount();
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    expect(screen.getByText(/No thumbnail yet/)).toBeVisible();
  });

  it("will not create a copy without a title", async () => {
    const { backend, user } = await mount();
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    const dialog = screen.getByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Title"));
    expect(
      within(dialog).getByRole("button", { name: "Create copy" }),
    ).toBeDisabled();
    await user.type(within(dialog).getByLabelText("Title"), "   {Enter}");
    expect(backend.copied).toEqual([]);
  });

  it("closes on Cancel and Escape without copying, and starts fresh when reopened", async () => {
    const { backend, user } = await mount();
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    await user.type(screen.getByLabelText("Title"), " edited");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Chemical bonds-copy");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(backend.copied).toEqual([]);
  });

  it("keeps the sheet open, locked while saving, and shows the error so the title survives a retry", async () => {
    const { backend, user } = await mount();
    let release = () => {};
    backend.copyGate = new Promise<void>((resolve) => (release = resolve));
    backend.failCopy = true;
    await user.click(screen.getByRole("button", { name: "Copy lesson" }));
    const dialog = screen.getByRole("dialog");
    const title = within(dialog).getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "Mine");
    await user.click(
      within(dialog).getByRole("button", { name: "Create copy" }),
    );
    expect(
      await within(dialog).findByRole("button", { name: "Creating copy…" }),
    ).toBeDisabled();
    expect(title).toBeDisabled();
    expect(
      within(dialog).getByRole("button", { name: "Cancel" }),
    ).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeVisible();
    release();
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Could not copy lesson. Try again.",
    );
    expect(title).toHaveValue("Mine");
    expect(screen.getByTestId("where")).toHaveTextContent(
      "/lessons/lesson_one",
    );
    backend.failCopy = false;
    backend.copyGate = null;
    await user.click(
      within(dialog).getByRole("button", { name: "Create copy" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("lesson_copy"),
    );
  });
});
