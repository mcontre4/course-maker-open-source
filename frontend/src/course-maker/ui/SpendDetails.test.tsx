import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  SpendDetails,
  StandaloneSpendDetails,
  formatSpend,
} from "./SpendDetails";
import { ApplicationContext } from "./application-context";
import {
  createApiCourseApplication,
  createCourseApplication,
} from "../composition";
import { courseFixture } from "../testing/course-fixture";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import type { CourseResponse } from "../application/dto";

const total = {
  knownUsd: "0.003456",
  calls: 2,
  pendingCalls: 0,
  estimatedCalls: 0,
  inputTokens: 100,
  outputTokens: 50,
};

describe("AI spend", () => {
  it.each([
    [["direct"], "Direct LLM"],
    [["codex"], "Codex CLI"],
    [["codex", "direct"], "Codex CLI, Direct LLM"],
    [[null], "openrouter · override-model"],
  ] as const)(
    "shows recorded engines %j for animation workers",
    async (backends, label) => {
      const stages = [
        "assets",
        "animation",
        "visual_review",
        "animation_repair",
      ];
      const course: CourseResponse = {
        ...courseFixture(),
        spend: {
          currency: "USD",
          total,
          shared: total,
          lessons: [],
          breakdown: stages.map((stage) => ({
            lessonId: "lesson",
            stage,
            provider: "openrouter",
            model: "override-model",
            total,
          })),
          steps: stages.flatMap((stage) =>
            backends.map((backend, index) => ({
              id: `${stage}-${index}`,
              lessonId: "lesson",
              stage,
              backend,
              startedAt: 100,
              finishedAt: index === 0 ? null : 110,
            })),
          ),
        },
      };
      const app = createCourseApplication(
        { getItem: () => null, setItem: () => {} },
        { next: () => "id" },
      );
      render(
        <QueryClientProvider client={new QueryClient()}>
          <ApplicationContext.Provider value={app}>
            <SpendDetails course={course} lessonId="lesson" />
          </ApplicationContext.Provider>
        </QueryClientProvider>,
      );
      await userEvent.click(screen.getByText("Lesson AI spend"));
      for (const row of screen.getAllByRole("row").slice(1)) {
        expect(within(row).getAllByRole("cell")[0]).toHaveTextContent(label);
        expect(
          within(row).getByText("openrouter · override-model"),
        ).toBeVisible();
        if (!backends.some((backend) => backend === "codex")) {
          expect(within(row).queryByText(/Codex CLI/)).not.toBeInTheDocument();
        }
      }
    },
  );

  it("keeps small charges visible and distinguishes pending and estimated costs", () => {
    expect(formatSpend(total)).toBe("$0.0035");
    expect(formatSpend({ ...total, knownUsd: "0", pendingCalls: 2 })).toBe(
      "$0.00 + pending",
    );
    expect(formatSpend({ ...total, pendingCalls: 2 })).toBe(
      "$0.0035 + pending",
    );
    expect(formatSpend({ ...total, knownUsd: "0.00000001" })).toBe("<$0.0001");
    expect(formatSpend({ ...total, pendingCalls: 1, estimatedCalls: 1 })).toBe(
      "≈$0.0035 + pending",
    );
  });

  it("keeps confirmed animation and review spend visible while requests are pending", async () => {
    const pendingTotal = { ...total, knownUsd: "0", pendingCalls: 2 };
    const course: CourseResponse = {
      ...courseFixture(),
      spend: {
        currency: "USD",
        total: pendingTotal,
        shared: total,
        lessons: [{ lessonId: "lesson", total: pendingTotal }],
        breakdown: ["animation", "visual_review"].map((stage) => ({
          lessonId: "lesson",
          stage,
          provider: "openrouter",
          model: "test-model",
          total: pendingTotal,
        })),
        steps: ["animation", "visual_review"].map((stage) => ({
          id: stage,
          lessonId: "lesson",
          stage,
          backend: "direct",
          startedAt: Date.now() / 1000,
          finishedAt: null,
        })),
      },
    };
    const app = createCourseApplication(
      { getItem: () => null, setItem: () => {} },
      { next: () => "id" },
    );
    const view = (value: CourseResponse) => (
      <QueryClientProvider client={new QueryClient()}>
        <ApplicationContext.Provider value={app}>
          <SpendDetails course={value} lessonId="lesson" />
        </ApplicationContext.Provider>
      </QueryClientProvider>
    );
    const { rerender } = render(view(course));
    await userEvent.click(screen.getByText("Lesson AI spend"));
    const row = (stage: string) =>
      screen.getByRole("rowheader", { name: stage }).closest("tr")!;
    for (const stage of ["Video / animation", "Visual review"]) {
      expect(
        within(row(stage)).getByText("$0.00 + pending + processing"),
      ).toBeVisible();
    }
    expect(screen.queryByText(/Speech credits need/)).not.toBeInTheDocument();
    const settled = { ...total, knownUsd: "0.42" };
    rerender(
      view({
        ...course,
        spend: {
          ...course.spend!,
          breakdown: course.spend!.breakdown.map((entry) => ({
            ...entry,
            total: entry.stage === "animation" ? settled : pendingTotal,
          })),
          steps: course.spend!.steps!.map((step) => ({
            ...step,
            finishedAt: step.stage === "animation" ? step.startedAt + 20 : null,
          })),
        },
      }),
    );
    expect(within(row("Video / animation")).getByText("$0.42")).toBeVisible();
    expect(
      within(row("Visual review")).getByText("$0.00 + pending + processing"),
    ).toBeVisible();
    rerender(
      view({
        ...course,
        spend: {
          ...course.spend!,
          breakdown: course.spend!.breakdown.map((entry) => ({
            ...entry,
            total: { ...settled, calls: 3, pendingCalls: 1 },
          })),
        },
      }),
    );
    for (const stage of ["Video / animation", "Visual review"]) {
      expect(
        within(row(stage)).getByText("$0.42 + pending + processing"),
      ).toBeVisible();
    }
  });

  it("automatically reconciles delayed course and standalone billing after workers finish", async () => {
    const makeCourse = (
      id: string,
      provider = "openrouter",
    ): CourseResponse => ({
      ...courseFixture(),
      id,
      spend: {
        currency: "USD",
        total: { ...total, knownUsd: "0", pendingCalls: total.calls },
        shared: total,
        lessons: [],
        breakdown: [
          {
            lessonId: id,
            stage: "animation",
            provider,
            model: "model",
            total: { ...total, knownUsd: "0", pendingCalls: total.calls },
          },
        ],
        steps: [
          {
            id: `step-${id}`,
            lessonId: id,
            stage: "animation",
            startedAt: 100,
            finishedAt: 120,
            backend: "direct",
          },
        ],
      },
    });
    const course = makeCourse("course");
    const speech = makeCourse("speech", "elevenlabs");
    const backend = new MemoryStandaloneBackend();
    const lesson = {
      ...(await backend.create({ title: "Test lesson", minutes: 1 })),
      spend: makeCourse("lesson_one").spend,
    };
    const settle = (value: CourseResponse["spend"]) => ({
      ...value!,
      total,
      lessons: [{ lessonId: lesson.id, total }],
      breakdown: value!.breakdown.map((entry) => ({ ...entry, total })),
    });
    const refreshed: string[] = [];
    const api = createApiCourseApplication(async () => {
      throw new Error("Unexpected transport request");
    });
    const app = {
      ...api,
      refreshSpend: {
        execute: async (id: string) => {
          refreshed.push(id);
          return { ...course, spend: settle(course.spend) };
        },
      },
      lessons: {
        ...api.lessons!,
        refreshSpend: {
          execute: async (id: string) => {
            refreshed.push(id);
            return { ...lesson, spend: settle(lesson.spend) };
          },
        },
      },
    };
    const client = new QueryClient();
    const view = (settled: boolean) => (
      <QueryClientProvider client={client}>
        <ApplicationContext.Provider value={app}>
          <SpendDetails
            course={
              settled ? { ...course, spend: settle(course.spend) } : course
            }
          />
          <SpendDetails course={speech} />
          <SpendDetails
            course={
              settled ? { ...course, spend: settle(course.spend) } : course
            }
            lessonId="course"
          />
          <StandaloneSpendDetails
            lesson={
              settled ? { ...lesson, spend: settle(lesson.spend) } : lesson
            }
          />
        </ApplicationContext.Provider>
      </QueryClientProvider>
    );
    const { rerender } = render(view(false));
    expect(refreshed).toEqual([]);
    await waitFor(
      () => {
        expect(refreshed.sort()).toEqual(["course", "lesson_one"]);
        expect(client.getQueryData(["courses", "course"])).toEqual({
          ...course,
          spend: settle(course.spend),
        });
        expect(client.getQueryData(["lessons", lesson.id])).toEqual({
          ...lesson,
          spend: settle(lesson.spend),
        });
      },
      { timeout: 6500 },
    );
    rerender(view(true));
    expect(
      screen.getAllByText("Lesson AI spend")[1].closest("summary"),
    ).toHaveTextContent("$0.0035");
    expect(
      screen.getAllByText("Lesson AI spend")[1].closest("summary"),
    ).not.toHaveTextContent("pending");
  }, 10000);

  it("shows a compact disclosure with lesson-only model costs", async () => {
    const course: CourseResponse = {
      ...courseFixture(),
      spend: {
        currency: "USD",
        total,
        shared: total,
        lessons: [{ lessonId: "lesson", total }],
        breakdown: [
          {
            lessonId: "lesson",
            stage: "lesson",
            provider: "openrouter",
            model: "test-model",
            total,
          },
          {
            lessonId: null,
            stage: "syllabus",
            provider: "openrouter",
            model: "shared-model",
            total,
          },
        ],
      },
    };
    const app = createCourseApplication(
      { getItem: () => null, setItem: () => {} },
      { next: () => "id" },
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ApplicationContext.Provider value={app}>
          <SpendDetails course={course} lessonId="lesson" />
        </ApplicationContext.Provider>
      </QueryClientProvider>,
    );
    const summary = screen.getByText("Lesson AI spend");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(summary);
    expect(summary.closest("details")).toHaveAttribute("open");
    expect(screen.getByText("openrouter · test-model")).toBeVisible();
    expect(screen.queryByText(/shared-model/)).not.toBeInTheDocument();
  });
  it("shows Codex steps before charges and removes processing when they finish", async () => {
    const app = createCourseApplication(
      { getItem: () => null, setItem: () => {} },
      { next: () => "id" },
    );
    const startedAt = Date.now() / 1000 - 75;
    const course: CourseResponse = {
      ...courseFixture(),
      spend: {
        currency: "USD",
        total,
        shared: total,
        lessons: [],
        breakdown: [],
        steps: [
          {
            id: "assets",
            lessonId: "lesson",
            stage: "assets",
            backend: "codex",
            startedAt: startedAt - 30,
            finishedAt: startedAt,
          },
          {
            id: "animation",
            lessonId: "lesson",
            stage: "animation",
            backend: "codex",
            startedAt,
            finishedAt: null,
          },
          {
            id: "other",
            lessonId: "other",
            stage: "guide",
            startedAt,
            finishedAt: null,
          },
        ],
      },
    };
    const client = new QueryClient();
    const view = (value: CourseResponse) => (
      <QueryClientProvider client={client}>
        <ApplicationContext.Provider value={app}>
          <SpendDetails course={value} lessonId="lesson" />
        </ApplicationContext.Provider>
      </QueryClientProvider>
    );
    const { rerender } = render(view(course));
    await userEvent.click(screen.getByText("Lesson AI spend"));
    const table = screen.getByRole("table", { name: "AI spend by step" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((cell) => cell.textContent),
    ).toEqual(["Step", "Agent", "Time", "Spend"]);
    const assets = within(table).getByText("Asset generation").closest("tr")!;
    expect(within(assets).getByText("Codex CLI")).toBeVisible();
    expect(within(assets).getByText("30s")).toBeVisible();
    expect(within(assets).queryByText(/processing/)).not.toBeInTheDocument();
    expect(within(table).getByText(/processing/)).toBeVisible();
    expect(within(table).getByText(/1m 1[56]s/)).toBeVisible();
    expect(within(table).queryByText("Guide")).not.toBeInTheDocument();
    rerender(
      view({
        ...course,
        spend: {
          ...course.spend!,
          steps: course.spend!.steps!.map((step) => ({
            ...step,
            finishedAt: step.finishedAt ?? startedAt + 80,
          })),
        },
      }),
    );
    expect(screen.queryByText(/processing/)).not.toBeInTheDocument();
    expect(within(table).getByText("1m 20s")).toBeVisible();
  });

  it.each([
    ["openai/gpt-6-luna", "openai/gpt-6-luna"],
    ["openai/gpt-6-luna:fast", "openai/gpt-6-luna:fast"],
    ["openai/gpt-6-luna::fast", "openai/gpt-6-luna:fast"],
  ])(
    "shows %s with review, repair and rendering costs and elapsed time",
    async (model, modelLabel) => {
      const stages = ["visual_review", "animation_repair", "render"];
      const course: CourseResponse = {
        ...courseFixture(),
        spend: {
          currency: "USD",
          total,
          shared: total,
          lessons: [{ lessonId: "lesson", total }],
          breakdown: stages
            .slice(0, 2)
            .reverse()
            .map((stage) => ({
              lessonId: "lesson",
              stage,
              provider: "openrouter",
              model,
              total,
            })),
          steps: stages.map((stage, i) => ({
            id: stage,
            lessonId: "lesson",
            stage,
            startedAt: 100,
            finishedAt: 110 + i * 10,
            backend: stage === "render" ? null : "codex",
          })),
        },
      };
      const app = createCourseApplication(
        { getItem: () => null, setItem: () => {} },
        { next: () => "id" },
      );
      render(
        <QueryClientProvider client={new QueryClient()}>
          <ApplicationContext.Provider value={app}>
            <SpendDetails course={course} lessonId="lesson" />
          </ApplicationContext.Provider>
        </QueryClientProvider>,
      );
      await userEvent.click(screen.getByText("Lesson AI spend"));
      expect(
        screen.getAllByRole("rowheader").map((cell) => cell.textContent),
      ).toEqual(["Visual review", "Visual repair", "Rendering & verification"]);
      for (const [label, elapsed] of [
        ["Visual review", "10s"],
        ["Visual repair", "20s"],
      ]) {
        const row = screen
          .getByRole("rowheader", { name: label })
          .closest("tr")!;
        expect(within(row).getByText("Codex CLI")).toBeVisible();
        expect(
          within(row).getByText(`openrouter · ${modelLabel}`),
        ).toBeVisible();
        expect(within(row).getByText(elapsed)).toBeVisible();
        expect(within(row).getByText("$0.0035")).toBeVisible();
      }
      const renderRow = screen
        .getByRole("rowheader", { name: "Rendering & verification" })
        .closest("tr")!;
      expect(within(renderRow).getByText("Video renderer")).toBeVisible();
      expect(within(renderRow).getByText("30s")).toBeVisible();
      expect(within(renderRow).getByText("—")).toBeVisible();
    },
  );
});
