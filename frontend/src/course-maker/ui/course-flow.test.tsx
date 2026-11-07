import { recommendedCourses } from "./course-catalog";
import { describe, expect, it } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../../App";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import type { CourseApplication } from "../application/use-cases";
import type { KeyValueStorage } from "../adapters/persistence/browser-course-repository";
import { createDemoCourses } from "../adapters/demo/seed-courses";

class MemoryStorage implements KeyValueStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}
function mount(
  storage = new MemoryStorage(),
  route = "/",
  listCourses?: CourseApplication["listCourses"],
) {
  const app = createCourseApplication(storage, {
    next: () => "course_created",
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    app,
    ...render(
      <ApplicationContext.Provider
        value={{
          ...app,
          listCourses: listCourses ?? app.listCourses,
          creators: {
            own: async () => ({
              id: "user_test",
              name: "Creator",
              picture: null,
            }),
            save: async (profile) => ({ id: "user_test", ...profile }),
            page: async () => ({
              creator: { id: "user_test", name: "Creator", picture: null },
              lessons: [],
              courses: [],
            }),
            watch: async () => {
              throw new Error("No media in search fixture");
            },
            discover: async () => ({
              lessons: [],
              courses: recommendedCourses.map((course) => ({
                id: course.id,
                title: course.title,
                image: "",
                description: [
                  course.description,
                  course.topic,
                  ...course.subtopics,
                ].join(" · "),
                lessons: [
                  {
                    id: "lesson_" + course.id,
                    courseId: course.id,
                    title: "Introduction",
                    minutes: 3,
                    image: "",
                    videoUrl: "/test.mp4",
                  },
                ],
              })),
            }),
          },
        }}
      >
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={[route]}>
            <App />
          </MemoryRouter>
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    ),
  };
}
describe("Course Maker demo flow", () => {
  it("keeps an IME confirmation from submitting search and closes suggestions when tabbing away", async () => {
    const user = userEvent.setup();
    mount();
    const input = screen.getByRole("combobox", {
      name: "Search courses and lessons",
    });
    await user.type(input, "python");
    await screen.findByRole("listbox");
    expect(fireEvent.keyDown(input, { key: "Enter", isComposing: true })).toBe(
      false,
    );
    expect(input).toHaveFocus();
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    await user.tab();
    expect(screen.getByRole("button", { name: "Search" })).toHaveFocus();
    await user.tab();
    const allResults = screen.getByRole("link", {
      name: "View all results for “python” →",
    });
    expect(allResults).toHaveFocus();
    await user.tab();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("suggests at most five courses while typing and opens a saved course with the keyboard", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/explore");
    const input = screen.getByRole("combobox", {
      name: "Search courses and lessons",
    });
    await user.type(input, "a");
    const list = await screen.findByRole("listbox", {
      name: "Course and lesson suggestions",
    });
    await waitFor(() =>
      expect(within(list).getAllByRole("option")).toHaveLength(5),
    );
    expect(
      screen.getByRole("heading", { name: "All courses" }),
    ).toBeInTheDocument();
    await user.clear(input);
    await user.type(input, "PYTHON");
    await waitFor(() =>
      expect(
        within(screen.getByRole("listbox")).getAllByRole("option"),
      ).toHaveLength(2),
    );
    await user.keyboard("{ArrowDown}");
    expect(
      screen.getByRole("option", { name: /Python for everyday life/ }),
    ).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Enter}");
    expect(
      await screen.findByRole("heading", { name: "Python for everyday life" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("opens all real results without creating a course", async () => {
    const user = userEvent.setup();
    const { app } = mount();
    const input = screen.getByRole("combobox", {
      name: "Search courses and lessons",
    });
    await user.type(input, "python");
    const published = await screen.findByRole("option", {
      name: /Python for curious minds/,
    });
    expect(published).toHaveAttribute(
      "href",
      "/watch/lessons/lesson_python?course=python",
    );
    await user.click(
      screen.getByRole("link", { name: "View all results for “python” →" }),
    );
    const results = screen.getByRole("region", {
      name: "Find courses and lessons",
    });
    await waitFor(() =>
      expect(within(results).getByRole("status")).toHaveTextContent(
        "2 courses found",
      ),
    );
    expect(await app.listCourses.execute()).toHaveLength(2);
  });

  it("dismisses suggestions and recovers from no matches and blank queries", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/explore");
    const input = screen.getByRole("combobox", {
      name: "Search courses and lessons",
    });
    await user.type(input, "python");
    await screen.findByRole("option", { name: /Python for curious minds/ });
    await user.keyboard("{ArrowUp}");
    expect(
      screen.getByRole("option", { name: /Python for curious minds/ }),
    ).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Escape}");
    expect(input).toHaveFocus();
    expect(input).toHaveAttribute("aria-expanded", "false");
    await user.click(input);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    await user.click(screen.getByRole("heading", { name: "All courses" }));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.clear(input);
    await user.type(input, "nothing-matches-this");
    expect(
      await screen.findByText(
        "No courses or lessons found. Try another title.",
      ),
    ).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("heading", { name: "No courses or lessons found" }),
    ).toBeInTheDocument();
    await user.clear(
      screen.getByRole("combobox", { name: "Search courses and lessons" }),
    );
    await user.type(
      screen.getByRole("combobox", { name: "Search courses and lessons" }),
      "   ",
    );
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("heading", { name: "All courses" }),
    ).toBeInTheDocument();
  });

  it("reports a library failure and retries it without losing the query", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    const saved = createCourseApplication(new MemoryStorage(), {
      next: () => "unused",
    });
    mount(new MemoryStorage(), "/courses/new", {
      execute: async () => {
        attempts += 1;
        if (attempts === 1) throw new Error("Library unavailable");
        return saved.listCourses.execute();
      },
    });
    await user.type(
      screen.getByRole("combobox", { name: "Search courses and lessons" }),
      "python",
    );
    expect(
      await screen.findByText("Some results are unavailable. Please retry."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry search" }));
    expect(
      await screen.findByRole("option", { name: /Python for everyday life/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Search courses and lessons" }),
    ).toHaveValue("python");
  });

  it("searches the catalog and library globally after browsing a subtopic", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/explore/engineering?sub=Thermodynamics");
    await screen.findByRole("heading", {
      name: "Thermodynamics in everyday life",
    });
    await user.type(
      screen.getByRole("combobox", { name: "Search courses and lessons" }),
      "PYTHON",
    );
    await user.click(screen.getByRole("button", { name: "Search" }));
    const results = screen.getByRole("region", {
      name: "Find courses and lessons",
    });
    expect(
      within(results).getByRole("heading", {
        name: "Python for curious minds",
      }),
    ).toBeInTheDocument();
    expect(
      within(results).getByRole("link", { name: /Python for everyday life/ }),
    ).toBeInTheDocument();
    expect(within(results).getByRole("status")).toHaveTextContent(
      "2 courses found",
    );
    expect(results).toHaveFocus();
  });

  it("explores subtopics independently of a previous search and resets the search field", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/explore?q=python");
    await screen.findByRole("heading", { name: "Python for curious minds" });
    await user.click(screen.getByText("Explore"));
    await user.click(screen.getByRole("link", { name: "Thermodynamics" }));
    const results = await screen.findByRole("region", {
      name: "Thermodynamics courses",
    });
    expect(
      within(results).getByRole("heading", {
        name: "Thermodynamics in everyday life",
      }),
    ).toBeInTheDocument();
    expect(
      within(results).queryByRole("heading", {
        name: "Python for curious minds",
      }),
    ).not.toBeInTheDocument();
    expect(within(results).getByRole("status")).toHaveTextContent("1 course");
    expect(
      screen.getByRole("combobox", { name: "Search courses and lessons" }),
    ).toHaveValue("");
    expect(screen.getByText("Explore").closest("details")).not.toHaveAttribute(
      "open",
    );
  });

  it("dismisses Explore with Escape and outside clicks", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/explore");
    const heading = await screen.findByRole("heading", {
      name: "All courses",
    });
    const explore = screen.getByText("Explore");
    await user.click(explore);
    expect(explore.closest("details")).toHaveAttribute("open");
    await user.keyboard("{Escape}");
    expect(explore.closest("details")).not.toHaveAttribute("open");
    expect(explore).toHaveFocus();
    await user.click(explore);
    await user.click(heading);
    expect(explore.closest("details")).not.toHaveAttribute("open");
  });

  it("recovers from an empty search and filters the catalog by topic", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/explore?q=unmatched-course");
    await screen.findByRole("heading", { name: "No courses or lessons found" });
    await user.click(screen.getByRole("link", { name: "Show all courses →" }));
    expect(
      screen.getByRole("heading", { name: "All courses" }),
    ).toBeInTheDocument();
    await user.click(
      within(screen.getByRole("navigation", { name: "Topics" })).getByRole(
        "link",
        { name: /Engineering/ },
      ),
    );
    const results = await screen.findByRole("region", {
      name: "Engineering courses",
    });
    expect(within(results).getByRole("status")).toHaveTextContent("2 courses");
    expect(
      within(results).getByRole("heading", { name: "Circuits to robots" }),
    ).toBeVisible();
    expect(
      within(results).getAllByRole("link", { name: "Start course →" }),
    ).toHaveLength(2);
  });

  it("keeps the entered values when switching duration modes", async () => {
    const user = userEvent.setup();
    mount(new MemoryStorage(), "/courses/new");
    const weeks = screen.getByLabelText("Course duration (weeks)");
    await user.clear(weeks);
    await user.type(weeks, "6");
    const weekly = screen.getByLabelText("Hours per week");
    await user.clear(weekly);
    await user.type(weekly, "8");
    await user.click(screen.getByLabelText("Total hours"));
    const hours = screen.getByLabelText("Total learning hours");
    await user.clear(hours);
    await user.type(hours, "5");
    await user.click(screen.getByLabelText("Weekly schedule"));
    expect(screen.getByLabelText("Course duration (weeks)")).toHaveValue(6);
    expect(screen.getByLabelText("Hours per week")).toHaveValue(8);
    await user.click(screen.getByLabelText("Total hours"));
    expect(screen.getByLabelText("Total learning hours")).toHaveValue(5);
  });
  it("creates, edits, and approves a short course, with no syllabus images", async () => {
    const user = userEvent.setup();
    const { app } = mount();
    await user.click(
      await screen.findByRole("link", { name: "Create a course" }),
    );
    await user.type(
      screen.getByLabelText("Course title"),
      "Python in an afternoon",
    );
    await user.type(
      screen.getByLabelText("What would you like to learn?"),
      "Help me get started with Python.",
    );
    await user.click(screen.getByLabelText("Total hours"));
    await user.click(
      screen.getByRole("button", { name: "Build my syllabus →" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "A learning path, made for you.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Detailed syllabus").querySelector("img"),
    ).toBeNull();
    await user.type(
      screen.getByLabelText("What would you like to cover?"),
      "Debug a small script",
    );
    await user.click(screen.getByRole("button", { name: "Add topic ↑" }));
    await waitFor(() =>
      expect(
        screen.getAllByText("Debug a small script").length,
      ).toBeGreaterThan(0),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Approve syllabus & create first lesson →",
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Your syllabus is approved.",
      }),
    ).toBeInTheDocument();
    expect((await app.getCourse.execute("course_created")).status).toBe(
      "ready",
    );
  });
  it("unlocks the quiz after video playback ends and persists quiz completion", async () => {
    const user = userEvent.setup();
    const storage = new MemoryStorage();
    storage.setItem(
      "course-maker:v1",
      JSON.stringify({
        version: 1,
        courses: createDemoCourses().map((course) => ({
          ...course,
          chapters: course.chapters.map((chapter) => ({
            ...chapter,
            lessons: chapter.lessons.map((lesson) => ({
              ...lesson,
              videoUrl:
                lesson.id === "lesson_5"
                  ? "/test-media/lists.mp4"
                  : lesson.videoUrl,
            })),
          })),
        })),
      }),
    );
    const mounted = mount(
      storage,
      "/courses/course_python_demo/lessons/lesson_5",
    );
    const takeQuiz = await screen.findByRole("button", {
      name: "Take the lesson quiz →",
    });
    expect(takeQuiz).toBeDisabled();
    const video = screen.getByLabelText("A place for everything: lists video");
    fireEvent.ended(video);
    await waitFor(() => expect(takeQuiz).toBeEnabled());
    await user.click(takeQuiz);
    await user.click(screen.getByRole("radio", { name: /plans.append/ }));
    await user.click(screen.getByRole("button", { name: "Next question →" }));
    await user.click(screen.getByRole("radio", { name: "0" }));
    await user.click(screen.getByRole("button", { name: "Next question →" }));
    await user.click(screen.getByRole("radio", { name: /Use a for loop/ }));
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    expect(
      await screen.findByRole("heading", {
        name: "One more lesson. One step further.",
      }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("5 lessons completed")).toBeInTheDocument(),
    );
    mounted.unmount();
    mount(storage);
    expect(
      await screen.findByText("5 of 16 lessons complete"),
    ).toBeInTheDocument();
  });
  it("shows a useful error for a missing course", async () => {
    mount(new MemoryStorage(), "/courses/missing/syllabus");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not be found",
    );
  });
  it("shows video availability instead of a slideshow and keeps the quiz locked", async () => {
    mount(new MemoryStorage(), "/courses/course_python_demo/lessons/lesson_5");
    expect(
      await screen.findByRole("status", { name: "Video not ready" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Next concept/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Mark preview/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Take the lesson quiz →" }),
    ).toBeDisabled();
  });
  it("rejects a schedule above the maximum before creating a draft", async () => {
    const user = userEvent.setup();
    const { app } = mount(new MemoryStorage(), "/courses/new");
    await user.type(screen.getByLabelText("Course title"), "A longer course");
    await user.type(
      screen.getByLabelText("What would you like to learn?"),
      "My learning goal",
    );
    const weeks = screen.getByLabelText("Course duration (weeks)");
    await user.clear(weeks);
    await user.type(weeks, "13");
    await user.click(
      screen.getByRole("button", { name: "Build my syllabus →" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Choose up to 12 weeks.",
    );
    expect(await app.listCourses.execute()).toHaveLength(2);
  });
});

it("saves course drafts explicitly, restores details, and filters the workspace", async () => {
  const storage = new MemoryStorage();
  const user = userEvent.setup();
  const view = mount(storage, "/courses/new");
  await user.type(screen.getByLabelText("Course title"), "Drawing light");
  await user.type(
    screen.getByLabelText("What would you like to learn?"),
    "Learn to draw shadows",
  );
  await user.click(screen.getByRole("button", { name: "Save as draft" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Save as draft" }),
    ).toBeDisabled(),
  );
  expect(
    (await view.app.getCourse.execute("course_created")).chapters,
  ).toHaveLength(0);
  await user.type(screen.getByLabelText("Course title"), " and shade");
  expect(screen.getByRole("button", { name: "Save as draft" })).toBeEnabled();
  expect((await view.app.getCourse.execute("course_created")).title).toBe(
    "Drawing light",
  );
  await user.click(screen.getByRole("button", { name: "Save as draft" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Save as draft" }),
    ).toBeDisabled(),
  );
  view.unmount();
  mount(storage, "/workspace?status=draft");
  expect(
    await screen.findByRole("heading", { name: "Drawing light and shade" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "Python for everyday life" }),
  ).not.toBeInTheDocument();
  await user.type(
    screen.getByRole("searchbox", { name: "Search workspace" }),
    "Drawing",
  );
  await user.click(screen.getByRole("link", { name: "Continue course" }));
  expect(await screen.findByLabelText("Course title")).toHaveValue(
    "Drawing light and shade",
  );
  await user.click(screen.getByRole("button", { name: "Build my syllabus →" }));
  expect(await screen.findByLabelText("Detailed syllabus")).toBeVisible();
});
