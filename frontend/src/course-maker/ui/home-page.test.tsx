import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "../../App";
import type { CourseResponse } from "../application/dto";
import type { Discovery, PublishedLesson } from "../application/creators";
import type { LearningActivityLog } from "../application/learning-activity";
import type { CourseApplication } from "../application/use-cases";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";

function course(
  id: string,
  title: string,
  lessons: readonly string[],
  options: Partial<Pick<CourseResponse, "status" | "completed">> = {},
) {
  return {
    id,
    title,
    description: "",
    image: "python",
    status: "ready",
    completed: [],
    duration: { mode: "total", hours: 3 },
    reviewed: [],
    messages: [],
    chapters: [
      {
        id: "chapter",
        title: "Chapter",
        lessons: lessons.map((lesson) => ({ id: lesson, title: lesson })),
      },
    ],
    ...options,
  } as unknown as CourseResponse;
}

function published(id: string, title: string) {
  return {
    id,
    title,
    image: "story",
    minutes: 2,
    videoUrl: null,
    courseId: null,
  } satisfies PublishedLesson;
}

class MemoryStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

class RecordingLog implements LearningActivityLog {
  readonly recorded: string[] = [];
  constructor(
    private readonly opened: readonly {
      itemId: string;
      lastOpenedAt: string;
    }[] = [],
  ) {}
  async recent() {
    return this.opened;
  }
  async record(itemId: string) {
    this.recorded.push(itemId);
  }
}

function mountWithClient(discover: () => Promise<Discovery>) {
  return mount({ discover }).client;
}

function mount({
  courses = [],
  discovery = { lessons: [], courses: [] },
  log = new RecordingLog(),
  route = "/",
  discover,
}: {
  courses?: readonly CourseResponse[];
  discovery?: Discovery;
  log?: LearningActivityLog;
  route?: string;
  discover?: () => Promise<Discovery>;
}) {
  const app = createCourseApplication(new MemoryStorage(), {
    next: () => "course_created",
  });
  const value: CourseApplication = {
    ...app,
    ...(route === "/"
      ? { listCourses: { execute: async () => courses } as never }
      : {}),
    learningActivity: log,
    creators: {
      own: async () => ({ id: "user_test", name: "Creator", picture: null }),
      save: async () => ({ id: "user_test", name: "Creator", picture: null }),
      discover: discover ?? (async () => discovery),
      page: async () => {
        throw new Error("unused");
      },
      watch: async () => {
        throw new Error("unused");
      },
    },
  };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ApplicationContext.Provider value={value}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  return { app: value, client };
}

describe("homepage", () => {
  it("keeps the create card with both ways to start and how it works", async () => {
    mount({});
    const card = (
      await screen.findByRole("heading", {
        name: "What would you like to learn next?",
      })
    ).closest("section") as HTMLElement;
    expect(
      within(card).getByRole("link", { name: "Create a lesson" }),
    ).toHaveAttribute("href", "/lessons/new");
    expect(
      within(card).getByRole("link", { name: "Create your first course" }),
    ).toHaveAttribute("href", "/courses/new");
    expect(within(card).getByLabelText("How it works")).toBeVisible();
  });

  it("features the most recently opened work and resumes at the next lesson", async () => {
    mount({
      courses: [
        course("course_old", "Older course", ["a"]),
        course("course_new", "Recent course", ["one", "two"], {
          completed: ["one"],
        }),
      ],
      log: new RecordingLog([
        { itemId: "course_new", lastOpenedAt: "2026-11-01T10:00:00+00:00" },
        { itemId: "course_old", lastOpenedAt: "2026-11-01T09:00:00+00:00" },
      ]),
    });
    const feature = await screen.findByRole("region", {
      name: "Recent course",
    });
    expect(
      within(feature).getByText("Continue where you left off"),
    ).toBeVisible();
    expect(within(feature).getByText("Next: two")).toBeVisible();
    expect(within(feature).getByText("1 of 2 lessons complete")).toBeVisible();
    expect(
      within(feature).getByRole("link", { name: "Continue learning" }),
    ).toHaveAttribute("href", "/courses/course_new/lessons/two");
  });

  it("lists the rest of your work, without the featured item or finished courses", async () => {
    mount({
      courses: [
        course("course_a", "Featured course", ["a"]),
        course("course_b", "Second course", ["b"]),
        course("course_done", "Finished course", ["c"], { completed: ["c"] }),
        course("course_draft", "Draft course", [], { status: "draft" }),
      ],
    });
    const row = await screen.findByRole("region", {
      name: "More of your work",
    });
    expect(
      within(row).getByRole("link", { name: /Second course/ }),
    ).toHaveAttribute("href", "/courses/course_b/lessons/b");
    const draft = within(row).getByRole("link", { name: /Draft course/ });
    expect(draft).toHaveAttribute("href", "/courses/course_draft/syllabus");
    expect(within(draft).getByText("Ready for your review")).toBeVisible();
    expect(within(row).queryByText("Featured course")).not.toBeInTheDocument();
    expect(screen.queryByText("Finished course")).not.toBeInTheDocument();
  });

  it("features the newest public lesson on a first visit, without repeating it", async () => {
    mount({
      discovery: {
        lessons: [
          published("lesson_1", "Newest lesson title"),
          published("lesson_2", "Snakes"),
          published("lesson_3", "Snakes"),
          published("lesson_4", "Theranos"),
        ],
        courses: [],
      },
    });
    const feature = await screen.findByRole("region", {
      name: "Newest lesson title",
    });
    expect(
      within(feature).getByRole("link", { name: "Watch lesson" }),
    ).toHaveAttribute("href", "/watch/lessons/lesson_1");
    const row = screen.getByRole("region", { name: "Newest lessons" });
    expect(
      within(within(row).getByRole("list"))
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual([
      expect.stringContaining("Snakes"),
      expect.stringContaining("Theranos"),
    ]);
    expect(
      screen.queryByRole("region", { name: "More of your work" }),
    ).not.toBeInTheDocument();
  });

  it("shows published courses only when some exist", async () => {
    mount({
      discovery: {
        lessons: [],
        courses: [
          {
            id: "course_public",
            title: "A public course",
            description: "About it",
            image: "python",
            lessons: [published("lesson_9", "First")],
          },
        ],
      },
    });
    const row = await screen.findByRole("region", { name: "Newest courses" });
    expect(
      within(row).getByRole("link", { name: /A public course/ }),
    ).toHaveAttribute("href", "/watch/lessons/lesson_9");
  });

  it("leaves out empty rows", async () => {
    mount({});
    await screen.findByRole("region", { name: "Browse by topic" });
    await waitFor(() =>
      expect(screen.queryByRole("status")).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("region", { name: "Newest lessons" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Newest courses" }),
    ).not.toBeInTheDocument();
  });

  it("links every topic to its Explore page", async () => {
    mount({});
    const topics = await screen.findByRole("region", {
      name: "Browse by topic",
    });
    expect(
      within(topics).getByRole("link", { name: /Mathematics/ }),
    ).toHaveAttribute("href", "/explore/mathematics");
    expect(
      within(topics).getByRole("link", { name: "See all courses" }),
    ).toHaveAttribute("href", "/explore");
  });

  it("still shows your work when recent activity can't load", async () => {
    mount({
      courses: [course("course_a", "Still here", ["a"])],
      log: {
        recent: async () => {
          throw new Error("offline");
        },
        record: async () => undefined,
      },
    });
    expect(
      await screen.findByRole("region", { name: "Still here" }),
    ).toBeVisible();
  });

  it("offers a retry when new lessons can't load, and keeps the page usable", async () => {
    mount({
      discover: async () => {
        throw new Error("offline");
      },
    });
    const row = await screen.findByRole("region", { name: "Newest lessons" });
    expect(
      await within(row).findByRole("button", { name: "Try again" }),
    ).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Browse by topic" }),
    ).toBeVisible();
  });
});

describe("when new lessons fail to refresh", () => {
  it("keeps showing the lessons it already has, without an error", async () => {
    let calls = 0;
    const client = mountWithClient(async () => {
      calls += 1;
      if (calls > 1) throw new Error("offline");
      return {
        lessons: [
          published("lesson_1", "Kept lesson"),
          published("lesson_2", "Second"),
        ],
        courses: [],
      };
    });
    const row = await screen.findByRole("region", { name: "Newest lessons" });
    await act(async () => {
      await client.refetchQueries({ queryKey: ["public-discovery"] });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(client.getQueryState(["public-discovery"])?.status).toBe("error");
    expect(within(row).getByText("Second")).toBeVisible();
    expect(
      screen.getAllByRole("region", { name: "Newest lessons" }),
    ).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
  });

  it("hides the error panel while a retry is running", async () => {
    let attempt = 0;
    let finish: (value: Discovery) => void = () => undefined;
    mount({
      discover: () => {
        attempt += 1;
        return attempt === 1
          ? Promise.reject(new Error("offline"))
          : new Promise((resolve) => {
              finish = resolve;
            });
      },
    });
    await userEvent.click(
      await screen.findByRole("button", { name: "Try again" }),
    );
    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
    await act(async () =>
      finish({
        lessons: [published("lesson_1", "A"), published("lesson_2", "Back")],
        courses: [],
      }),
    );
    expect(await screen.findByText("Back")).toBeVisible();
  });
});

describe("recording what was opened", () => {
  it("records a course when its syllabus opens", async () => {
    const log = new RecordingLog();
    const seed = createCourseApplication(new MemoryStorage(), {
      next: () => "course_created",
    });
    const [first] = await seed.listCourses.execute();
    mount({ log, route: "/courses/" + first.id + "/syllabus" });
    await waitFor(() => expect(log.recorded).toEqual([first.id]));
  });

  it("records nothing for a course that can't be opened", async () => {
    const log = new RecordingLog();
    mount({ log, route: "/courses/missing/syllabus" });
    await screen.findByRole("alert");
    expect(log.recorded).toEqual([]);
  });

  it("does not record anything on the homepage itself", async () => {
    const log = new RecordingLog();
    mount({ log });
    await screen.findByRole("region", { name: "Browse by topic" });
    expect(log.recorded).toEqual([]);
  });
});
