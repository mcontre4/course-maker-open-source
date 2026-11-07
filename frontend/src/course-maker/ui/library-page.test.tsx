import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "../../App";
import type { CourseResponse } from "../application/dto";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import type { CourseApplication } from "../application/use-cases";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";

class MemoryStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

function course(id: string, title: string, status: "ready" | "draft") {
  return {
    id,
    title,
    description: "",
    image: "python",
    status,
    completed: [],
    duration: { mode: "total", hours: 3 },
    reviewed: [],
    messages: [],
    chapters: [
      { id: "chapter", title: "Chapter", lessons: [{ id: "a", title: "A" }] },
    ],
  } as unknown as CourseResponse;
}

function lesson(id: string, title: string, finished: boolean) {
  return {
    id,
    content: {
      title,
      image: "story",
      minutes: 3,
      animation: finished
        ? { status: "succeeded", reviewStatus: "approved" }
        : null,
      videoUrl: finished ? "https://example.com/v.mp4" : null,
      plan: null,
      storyboard: null,
      alignment: null,
    },
  } as unknown as StandaloneLessonResponse;
}

function mount(
  courses: readonly CourseResponse[],
  lessons: readonly StandaloneLessonResponse[],
  route = "/library",
  { withCreator = false, lessonsError = false } = {},
) {
  const app = createCourseApplication(new MemoryStorage(), {
    next: () => "course_created",
  });
  const value: CourseApplication = {
    ...app,
    listCourses: { execute: async () => courses } as never,
    lessons: {
      list: {
        execute: async () => {
          if (lessonsError) throw new Error("Lessons are unavailable");
          return lessons;
        },
      },
    } as never,
    ...(withCreator
      ? {
          creators: {
            own: async () => ({
              id: "user_test",
              name: "Creator",
              picture: null,
            }),
            discover: async () => ({ lessons: [], courses: [] }),
          } as never,
        }
      : {}),
  };
  render(
    <ApplicationContext.Provider value={value}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={[route]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
}

describe("my library", () => {
  it("lists started courses and watchable lessons, leaving drafts to My creations", async () => {
    mount(
      [
        course("course_a", "Started course", "ready"),
        course("course_b", "Draft course", "draft"),
      ],
      [
        lesson("lesson_a", "Finished lesson", true),
        lesson("lesson_b", "Lesson still in progress", false),
      ],
    );
    await screen.findByRole("heading", { name: "My library" });
    expect(
      await screen.findByRole("heading", { name: "Started course" }),
    ).toBeInTheDocument();
    const lessons = await screen.findByRole("region", { name: "Lessons" });
    expect(
      within(lessons).getByRole("link", { name: /Finished lesson/ }),
    ).toHaveAttribute("href", "/lessons/lesson_a");
    expect(screen.queryByText("Draft course")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Lesson still in progress"),
    ).not.toBeInTheDocument();
  });

  it("points to creating something when there is nothing to learn from yet", async () => {
    mount([course("course_b", "Draft course", "draft")], []);
    expect(
      await screen.findByRole("heading", { name: "Nothing to learn from yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Create a lesson →" }),
    ).toHaveAttribute("href", "/lessons/new");
  });
});

describe("my library when lessons fail", () => {
  it("still shows courses and reports the lesson error", async () => {
    mount([course("course_a", "Started course", "ready")], [], "/library", {
      lessonsError: true,
    });
    expect(
      await screen.findByRole("heading", { name: "Started course" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Nothing to learn from yet" }),
    ).not.toBeInTheDocument();
  });
});

describe("account menu", () => {
  it("leads with the public profile, then groups learning and creating", async () => {
    const user = userEvent.setup();
    mount([], [], "/explore", { withCreator: true });
    await user.click(await screen.findByLabelText("Account: Creator"));
    const profile = await screen.findByRole("link", {
      name: "View public profile",
    });
    expect(profile).toHaveAttribute("href", "/creators/user_test");
    const nav = screen.getByRole("navigation", { name: "Account navigation" });
    expect(
      within(nav)
        .getAllByRole("link")
        .map((link) => link.getAttribute("href")),
    ).toEqual(["/library", "/workspace", "/settings"]);
    expect(
      within(nav).getByRole("group", { name: "Learning" }),
    ).toContainElement(within(nav).getByRole("link", { name: "My library" }));
    expect(
      within(nav).getByRole("group", { name: "Creating" }),
    ).toContainElement(within(nav).getByRole("link", { name: "My creations" }));
  });

  it("keeps the old My Courses address working", async () => {
    mount([], [], "/my-courses");
    expect(
      await screen.findByRole("heading", { name: "My library" }),
    ).toBeInTheDocument();
  });
});
