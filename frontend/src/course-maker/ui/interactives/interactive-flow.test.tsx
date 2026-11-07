import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import {
  createBackendCourseApplication,
  createInteractiveApplications,
} from "../../composition";
import type { LessonInteractiveApplication } from "../../application/lesson-interactives";
import type { LearnerQuizApplication } from "../../application/lesson-quizzes";
import {
  AdvanceStandaloneLesson,
  CreateStandaloneLesson,
  GetStandaloneLesson,
  ListStandaloneLessons,
  PlanStandaloneLesson,
  PrepareStandaloneScript,
  SaveStandaloneOutline,
  SaveStandaloneScript,
  UpdateStandaloneLesson,
} from "../../application/standalone-lessons";
import { MemoryCourseBackend } from "../../testing/course-backend";
import { MemoryStandaloneBackend } from "../../testing/standalone-backend";
import { ApplicationContext } from "../application-context";
import { CreateLessonPage } from "../pages/CreateLessonPage";
import { StandaloneInteractiveStudioPage } from "../pages/InteractiveStudioPage";
import { PublicLessonPage } from "../pages/PublicLessonPage";
import { StandaloneLessonPage } from "../pages/StandaloneLessonPage";

const buildTime = 60_000;
const lessonPath = "/lessons/lesson_one";

/** Everything runs against the browser stand-in, with a clock the test moves. */
async function mount(
  backend: MemoryStandaloneBackend,
  route: string,
  seed?: (
    interactives: LessonInteractiveApplication,
    finishBuilds: () => void,
  ) => Promise<void>,
  learnerQuizzes?: LearnerQuizApplication,
) {
  const values = new Map<string, string>();
  let next = 0;
  const clock = { now: Date.parse("2026-11-01T00:00:00Z") };
  const app = {
    ...createBackendCourseApplication(new MemoryCourseBackend()),
    generationPreferences: backend.generationPreferences,
    learnerQuizzes,
    ...createInteractiveApplications(
      {
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => void values.set(key, value),
      },
      { next: () => String(++next) },
      () => new Date(clock.now),
    ),
    creators: {
      discover: async () => ({ lessons: [], courses: [] }),
      own: async () => ({ id: "user", name: "Sam", picture: null }),
      save: async () => ({ id: "user", name: "Sam", picture: null }),
      page: async () => ({
        creator: { id: "user", name: "Sam", picture: null },
        lessons: [],
        courses: [],
      }),
      watch: async (id: string) => ({
        creator: null,
        lesson: {
          id,
          title: "Pendulums",
          minutes: 3,
          image: "story",
          videoUrl: "/test-media/swing.mp4",
          courseId: null,
        },
      }),
    },
    lessons: {
      list: new ListStandaloneLessons(backend),
      get: new GetStandaloneLesson(backend),
      create: new CreateStandaloneLesson(backend),
      update: new UpdateStandaloneLesson(backend),
      saveOutline: new SaveStandaloneOutline(backend),
      saveScript: new SaveStandaloneScript(backend),
      prepareScript: new PrepareStandaloneScript(backend),
      plan: new PlanStandaloneLesson(backend),
      advance: new AdvanceStandaloneLesson(backend),
    },
  };
  await seed?.(app.interactives!, () => {
    clock.now += buildTime;
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/lessons/new" element={<CreateLessonPage />} />
            <Route
              path="/lessons/:lessonId"
              element={<StandaloneLessonPage />}
            />
            <Route
              path="/lessons/:lessonId/interactives/:interactiveId"
              element={<StandaloneInteractiveStudioPage />}
            />
            <Route
              path="/watch/lessons/:lessonId"
              element={<PublicLessonPage />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  return { clock, app };
}

/** One finished interactive that is already part of the lesson. */
async function seedPublished(
  interactives: LessonInteractiveApplication,
  finishBuilds: () => void,
) {
  const { id } = await interactives.create({
    lessonId: "lesson_one",
    brief: "A pendulum",
  });
  finishBuilds();
  await interactives.get({ lessonId: "lesson_one", id });
  await interactives.setPublishedVersion({
    lessonId: "lesson_one",
    id,
    version: 1,
  });
}

async function finishedLesson() {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({
    title: "Pendulums",
    description: "How they swing",
    minutes: 3,
  });
  backend.value = {
    ...created,
    content: {
      ...created.content,
      topics: ["pendulum period"],
      videoUrl: "/test-media/swing.mp4",
    },
  };
  return backend;
}

async function draftLesson() {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Pendulums",
    description: "How they swing",
    minutes: 3,
  });
  return backend;
}

const openFrame = (title: string) =>
  screen.findByTitle(title, undefined, { timeout: 4000 });

describe("lesson interactives", () => {
  it("goes from a description to a part of the lesson learners can open", async () => {
    const { clock } = await mount(await finishedLesson(), lessonPath);
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("link", { name: /Add an interactive/ }),
    );
    await user.type(
      await screen.findByLabelText("Describe your interactive"),
      "A pendulum with gravity and length controls",
    );
    await user.click(screen.getByRole("button", { name: "Build interactive" }));

    expect(
      await screen.findByRole("heading", { name: "Building your interactive" }),
    ).toBeVisible();

    clock.now += buildTime;
    await openFrame("Pendulum lab");
    expect(screen.getByTitle("Pendulum lab")).toHaveAttribute(
      "sandbox",
      "allow-scripts",
    );
    expect(screen.getByText("Not in lesson")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Add to lesson" }));
    expect(
      await screen.findByText("In lesson", { selector: ".workflow-status" }),
    ).toBeVisible();

    await user.click(
      screen.getByRole("link", { name: "See it in the lesson" }),
    );
    const path = await screen.findByRole("navigation", {
      name: "Parts of this lesson",
    });
    expect(
      within(path).getByRole("button", { name: /Pendulum lab/ }),
    ).toHaveAttribute("aria-current", "step");
    expect(
      await screen.findByRole("heading", { name: "Pendulum lab" }),
    ).toBeVisible();

    await user.click(
      screen.getByRole("checkbox", { name: /Double the length/ }),
    );
    expect(screen.getByText("1 of 4 tried")).toBeVisible();

    await user.click(within(path).getByRole("button", { name: /Watch/ }));
    expect(screen.queryByTitle("Pendulum lab")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Next: Pendulum lab" }),
    );
    // Going away and back keeps what the learner ticked.
    expect(await screen.findByText("1 of 4 tried")).toBeVisible();
  });

  it("keeps the version in use while a change builds, then asks before swapping", async () => {
    const { clock } = await mount(
      await finishedLesson(),
      `${lessonPath}?panel=interactives&edit=1`,
      seedPublished,
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: /Pendulum lab/ }));

    await user.type(
      await screen.findByLabelText("Ask for a change"),
      "Start on the Moon",
    );
    await user.click(screen.getByRole("button", { name: "Make this change" }));
    expect(await screen.findByText(/Building version 2/)).toBeVisible();
    expect(screen.getByTitle("Pendulum lab")).toBeVisible();
    expect(screen.getByLabelText("Ask for a change")).toBeDisabled();

    clock.now += buildTime;
    expect(
      await screen.findByRole(
        "button",
        { name: "Use version 2 in lesson" },
        { timeout: 4000 },
      ),
    ).toBeVisible();
    expect(screen.getByText("New version not in lesson")).toBeVisible();
    expect(screen.getByText(/Learners still get version 1/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Go back to this" }));
    expect(
      await screen.findByText("In lesson", { selector: ".workflow-status" }),
    ).toBeVisible();
  });

  it("offers a way forward when a build stops", async () => {
    const { clock } = await mount(
      await finishedLesson(),
      `${lessonPath}/interactives/new`,
    );
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("Describe your interactive"),
      "A pendulum #fail",
    );
    await user.click(screen.getByRole("button", { name: "Build interactive" }));
    await screen.findByRole("heading", { name: "Building your interactive" });
    clock.now += buildTime;
    expect(
      await screen.findByRole(
        "heading",
        { name: "This one didn’t finish" },
        { timeout: 4000 },
      ),
    ).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Try again" })[0]);
    expect(
      await screen.findByRole("heading", { name: "Building your interactive" }),
    ).toBeVisible();
  });

  it("explains itself and offers ideas from the lesson before anything exists", async () => {
    await mount(
      await draftLesson(),
      `${lessonPath}?step=review&panel=interactives`,
    );
    const user = userEvent.setup();
    expect(
      await screen.findByRole("heading", {
        name: "Let learners try it themselves",
      }),
    ).toBeVisible();
    const idea = screen.getAllByRole("button", { name: /A simulation for/ })[0];
    const text = idea.textContent;
    await user.click(idea);
    expect(
      await screen.findByLabelText("Describe your interactive"),
    ).toHaveValue(text);
  });

  it("stays reachable while the video is being made", async () => {
    const backend = await draftLesson();
    backend.value = {
      ...backend.value!,
      flow: "automatic",
      activeOperation: "lesson/automatic",
    };
    await mount(backend, lessonPath);
    expect(
      await screen.findByRole("heading", {
        name: "While you wait, add something learners can try",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Describe an interactive" }),
    ).toHaveAttribute("href", `${lessonPath}/interactives/new`);
  });

  it("builds interactives described before the lesson exists", async () => {
    const backend = new MemoryStandaloneBackend();
    const { app } = await mount(backend, "/lessons/new");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Lesson title"), "Pendulums");
    await user.click(
      screen.getByRole("radio", { name: /^Flat-Vector Science/ }),
    );
    await user.type(
      screen.getByLabelText("Describe an interactive"),
      "A pendulum to swing",
    );
    await user.click(
      screen.getByRole("button", { name: "+ Add this interactive" }),
    );
    expect(screen.getByText("A pendulum to swing")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(async () =>
      expect(
        (await app.interactives!.list("lesson_one")).map((item) => item.brief),
      ).toEqual(["A pendulum to swing"]),
    );
  });

  it("builds an interactive typed but never added to the list", async () => {
    const backend = new MemoryStandaloneBackend();
    const { app } = await mount(backend, "/lessons/new");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Lesson title"), "Pendulums");
    await user.click(
      screen.getByRole("radio", { name: /^Flat-Vector Science/ }),
    );
    await user.type(
      screen.getByLabelText("Describe an interactive"),
      "A pendulum to swing",
    );
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(async () =>
      expect(
        (await app.interactives!.list("lesson_one")).map((item) => item.brief),
      ).toEqual(["A pendulum to swing"]),
    );
  });

  it("leaves the studio after deleting an interactive", async () => {
    const { app } = await mount(
      await finishedLesson(),
      `${lessonPath}?panel=interactives&edit=1`,
      seedPublished,
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: /Pendulum lab/ }));
    await user.click(
      await screen.findByRole("button", { name: "For learners" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Delete interactive" }),
    );
    await user.click(screen.getByRole("button", { name: "Yes, delete it" }));
    expect(
      await screen.findByRole("heading", {
        name: "Let learners try it themselves",
      }),
    ).toBeVisible();
    expect(await app.interactives!.list("lesson_one")).toEqual([]);
  });

  it("shows learners only what is in the lesson, and no creator controls", async () => {
    await mount(
      await finishedLesson(),
      "/watch/lessons/lesson_one",
      async (interactives, finishBuilds) => {
        await seedPublished(interactives, finishBuilds);
        await interactives.create({ lessonId: "lesson_one", brief: "Draft" });
      },
    );
    const user = userEvent.setup();
    const path = await screen.findByRole("navigation", {
      name: "Parts of this lesson",
    });
    expect(within(path).getAllByRole("button")).toHaveLength(2);
    await user.click(
      within(path).getByRole("button", { name: /Pendulum lab/ }),
    );
    expect(await screen.findByTitle("Pendulum lab")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: /Edit interactive/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Add an interactive/ }),
    ).not.toBeInTheDocument();
  });
});

describe("public lesson quiz stop", () => {
  const quiz = {
    lessonId: "lesson_one",
    revision: 1,
    questions: [
      {
        id: "question_1",
        kind: "multiple_choice" as const,
        prompt: "Which swings slower?",
        options: ["Moon", "Earth"],
      },
    ],
  };

  it("keeps a learner's answers while they look back at the video", async () => {
    await mount(
      await finishedLesson(),
      "/watch/lessons/lesson_one",
      undefined,
      {
        get: async () => quiz,
        submit: async () => {
          throw new Error("Not used");
        },
        attempts: async () => [],
      },
    );
    const user = userEvent.setup();
    const path = await screen.findByRole("navigation", {
      name: "Parts of this lesson",
    });
    await user.click(
      within(path).getByRole("button", { name: /Check your understanding/ }),
    );
    await user.click(await screen.findByRole("radio", { name: /Moon/ }));
    await user.click(within(path).getByRole("button", { name: /Watch/ }));
    await user.click(
      within(path).getByRole("button", { name: /Check your understanding/ }),
    );
    expect(screen.getByRole("radio", { name: /Moon/ })).toBeChecked();
  });

  it("says so when the quiz can't be loaded", async () => {
    await mount(
      await finishedLesson(),
      "/watch/lessons/lesson_one",
      undefined,
      {
        get: async () => {
          throw new Error("The quiz request failed. Please try again.");
        },
        submit: async () => {
          throw new Error("Not used");
        },
        attempts: async () => [],
      },
    );
    expect(
      await screen.findByText("The quiz request failed. Please try again."),
    ).toBeVisible();
  });
});
