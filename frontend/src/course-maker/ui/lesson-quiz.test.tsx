import { describe, expect, it } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../../App";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import {
  createLessonQuizApplication,
  createServerLessonQuizApplication,
  type LessonQuiz,
  type LessonQuizBackend,
} from "../application/lesson-quizzes";
import { LessonQuizPanel } from "./LessonQuiz";
import { OutlineQuizGenerator } from "../adapters/demo/lesson-quiz-generator";
import { BrowserLessonQuizStore } from "../adapters/persistence/browser-lesson-quizzes";
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
} from "../application/standalone-lessons";
import { ApplicationContext } from "./application-context";

function mount(backend: MemoryStandaloneBackend) {
  const values = new Map<string, string>();
  const app = {
    ...createBackendCourseApplication(new MemoryCourseBackend()),
    generationPreferences: backend.generationPreferences,
    quizzes: createLessonQuizApplication(
      new BrowserLessonQuizStore({
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => void values.set(key, value),
      }),
      new OutlineQuizGenerator(),
    ),
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
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/lessons/new"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  return values;
}

async function finishAutomaticLesson() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("radio", { name: /^Flat-Vector Science/ }));
  await user.type(screen.getByLabelText("Lesson title"), "Chemical bonds");
  await user.type(
    screen.getByLabelText("What would you like to learn?"),
    "Explain bonding for beginners",
  );
  await user.click(screen.getByRole("radio", { name: "Automatic" }));
  await user.click(screen.getByRole("button", { name: "Create my lesson →" }));
  await screen.findByText("Your lesson video is ready to watch.");
  return user;
}

describe("lesson quiz", () => {
  it("keeps the draft's base revision when another tab changes the quiz", async () => {
    const lesson = await new MemoryStandaloneBackend().create({
      title: "Variables",
      minutes: 1,
    });
    class ConcurrentQuizBackend implements LessonQuizBackend {
      value: LessonQuiz = {
        lessonId: lesson.id,
        origin: "generated",
        revision: 1,
        questions: [
          {
            id: "question_1",
            kind: "multiple_choice",
            prompt: "Which value?",
            options: ["One", "Two"],
            correctIndex: 0,
            explanation: "One is correct.",
          },
        ],
      };
      revisions: (number | undefined)[] = [];
      async get() {
        return this.value;
      }
      async generate() {
        return this.value;
      }
      async save(request: Parameters<LessonQuizBackend["save"]>[0]) {
        this.revisions.push(request.expectedRevision);
        if (request.expectedRevision !== this.value.revision)
          throw new Error("Quiz changed; reload before continuing");
        this.value = {
          ...this.value,
          questions: request.questions,
          revision: this.value.revision! + 1,
        };
        return this.value;
      }
    }
    const backend = new ConcurrentQuizBackend();
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    render(
      <ApplicationContext.Provider
        value={{
          ...createBackendCourseApplication(new MemoryCourseBackend()),
          quizzes: createServerLessonQuizApplication(backend),
        }}
      >
        <QueryClientProvider client={client}>
          <LessonQuizPanel lesson={lesson} onDirtyChange={() => {}} />
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit quiz" }));
    await user.clear(screen.getByLabelText("Question 1 text"));
    await user.type(
      screen.getByLabelText("Question 1 text"),
      "My draft question",
    );
    backend.value = {
      ...backend.value,
      revision: 2,
      questions: backend.value.questions.map((q) => ({
        ...q,
        prompt: "Other tab's question",
      })),
    };
    act(() => client.setQueryData(["lesson-quiz", lesson.id], backend.value));
    await user.click(screen.getByRole("button", { name: "Save quiz" }));
    expect(
      await screen.findByText("Quiz changed; reload before continuing"),
    ).toBeVisible();
    expect(backend.revisions).toEqual([1]);
    expect(backend.value.questions[0].prompt).toBe("Other tab's question");
    expect(screen.getByLabelText("Question 1 text")).toHaveValue(
      "My draft question",
    );
  });

  it("drafts a quiz beside the finished video and lets the creator edit it", async () => {
    const values = mount(new MemoryStandaloneBackend());
    const user = await finishAutomaticLesson();

    await user.click(await screen.findByRole("button", { name: /^Quiz/ }));
    const preview = await screen.findByRole("region", {
      name: "Check your understanding",
    });
    expect(within(preview).getByText("What is shared?")).toBeVisible();

    await user.click(
      within(preview).getByRole("button", { name: "Edit quiz" }),
    );
    await user.click(await screen.findByRole("button", { name: "Edit quiz" }));
    await user.click(screen.getByRole("button", { name: "+ Add question" }));
    await user.type(
      screen.getByLabelText("Question 2 text"),
      "What holds atoms together?",
    );
    await user.type(
      screen.getByLabelText("Answer A of question 2"),
      "A shared bond",
    );
    await user.type(
      screen.getByLabelText("Answer B of question 2"),
      "Gravity alone",
    );
    await user.click(
      screen.getByLabelText("Mark answer B of question 2 as correct"),
    );
    await user.click(screen.getByRole("button", { name: "Save quiz" }));

    expect(await screen.findByText("What holds atoms together?")).toBeVisible();
    expect(
      screen.getByText(/2 questions · multiple choice · edited/),
    ).toBeVisible();
    const saved = JSON.parse(
      [...values.entries()].find(([key]) => key.includes("lesson-quiz"))![1],
    );
    expect(saved.questions[1]).toMatchObject({
      prompt: "What holds atoms together?",
      correctIndex: 1,
    });
  });

  it("explains what is missing instead of saving an incomplete question", async () => {
    mount(new MemoryStandaloneBackend());
    const user = await finishAutomaticLesson();
    await user.click(await screen.findByRole("button", { name: /^Quiz/ }));
    await user.click(await screen.findByRole("button", { name: "Edit quiz" }));
    await user.click(await screen.findByRole("button", { name: "Edit quiz" }));
    await user.click(screen.getByRole("button", { name: "+ Add question" }));
    await user.click(screen.getByRole("button", { name: "Save quiz" }));
    expect(
      (await screen.findAllByText(/Question 2: Write the question\./)).length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Save quiz" })).toBeEnabled();
  });
});
