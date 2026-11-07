import type { CancelGenerationRequest } from "../application/cancel-generation";
import { StrictMode } from "react";
import { describe, expect, it } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../../App";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import { GenerateThumbnail } from "../application/thumbnails";
import {
  ListStandaloneLessons,
  GetStandaloneLesson,
  CreateStandaloneLesson,
  UpdateStandaloneLesson,
  SaveStandaloneOutline,
  SaveStandaloneScript,
  PrepareStandaloneScript,
  PlanStandaloneLesson,
  AdvanceStandaloneLesson,
} from "../application/standalone-lessons";
import { styleFixture } from "../testing/style-fixture";
import { ApplicationContext } from "./application-context";

function HistoryBack() {
  const navigate = useNavigate();
  return <button onClick={() => navigate(-1)}>Go back in history</button>;
}
function mount(
  backend: MemoryStandaloneBackend,
  route = "/lessons/new",
  thumbnails?: Pick<GenerateThumbnail, "execute">,
  showHistory = false,
  cancelGeneration?: {
    execute(request: CancelGenerationRequest): Promise<boolean>;
  },
  routeState?: { startPlanning?: boolean },
) {
  const courses = new MemoryCourseBackend();
  const app = {
    ...createBackendCourseApplication(courses),
    thumbnails,
    cancelGeneration,
    generationPreferences: backend.generationPreferences,
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
  return {
    client,
    courses,
    ...render(
      <StrictMode>
        <ApplicationContext.Provider value={app}>
          <QueryClientProvider client={client}>
            <MemoryRouter
              initialEntries={[
                routeState ? { pathname: route, state: routeState } : route,
              ]}
            >
              {showHistory && <HistoryBack />}
              <App />
            </MemoryRouter>
          </QueryClientProvider>
        </ApplicationContext.Provider>
      </StrictMode>,
    ),
  };
}
async function createChemistry() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("radio", { name: /^Flat-Vector Science/ }));
  await user.type(screen.getByLabelText("Lesson title"), "Chemical bonds");
  await user.type(
    screen.getByLabelText("What would you like to learn?"),
    "Explain bonding for beginners",
  );
  await user.click(screen.getByRole("radio", { name: "Guided" }));
  await user.click(
    screen.getByRole("button", { name: "Build my lesson outline →" }),
  );
  return user;
}

describe("standalone lessons", () => {
  it("shows quality and speed as a creation step while technical settings stay collapsed", async () => {
    mount(new MemoryStandaloneBackend());
    const quality = screen.getByRole("group", { name: "Quality & speed" });
    expect(quality).toBeVisible();
    for (const name of ["Fast", "Balanced", "Pro"]) {
      expect(within(quality).getByText(name)).toBeVisible();
      expect(
        within(quality).getByRole("radio", { name }).closest("details"),
      ).toBeNull();
    }
    const technical = within(quality)
      .getByText("Technical settings")
      .closest("details");
    const model = within(quality).getByLabelText("Generation model");
    expect(technical).not.toHaveAttribute("open");
    expect(model).not.toBeVisible();
    await userEvent.click(within(quality).getByRole("radio", { name: "Fast" }));
    expect(within(quality).getByRole("radio", { name: "Fast" })).toBeChecked();
    expect(technical).not.toHaveAttribute("open");
    await userEvent.click(within(quality).getByText("Technical settings"));
    expect(model).toBeVisible();
  });

  it("keeps the required visual style visible with advanced settings closed", async () => {
    mount(new MemoryStandaloneBackend());
    const advanced = screen
      .getByText("Voice & delivery preferences")
      .closest("details");
    expect(advanced).not.toHaveAttribute("open");
    const visualStyle = screen.getByRole("radio", {
      name: /^Flat-Vector Science/,
    });
    expect(visualStyle).toBeVisible();
    expect(visualStyle).toBeRequired();
    expect(visualStyle.closest("details")).toBeNull();
    await createChemistry();
    expect(await screen.findByText("YOUR LESSON STUDIO")).toBeVisible();
  });

  describe("automatic flow", () => {
    async function fillLesson() {
      const user = userEvent.setup();
      await user.click(
        screen.getByRole("radio", { name: /^Flat-Vector Science/ }),
      );
      await user.type(screen.getByLabelText("Lesson title"), "Chemical bonds");
      await user.type(
        screen.getByLabelText("What would you like to learn?"),
        "Explain bonding for beginners",
      );
      return user;
    }

    it("lists automatic first and preselects it with fast quality", async () => {
      mount(new MemoryStandaloneBackend());
      const flows = screen
        .getAllByRole("radio")
        .filter((radio) =>
          ["Automatic", "Guided"].includes(radio.ariaLabel ?? ""),
        );
      expect(flows.map((radio) => radio.ariaLabel)).toEqual([
        "Automatic",
        "Guided",
      ]);
      expect(screen.getByRole("radio", { name: "Automatic" })).toBeChecked();
      expect(screen.getByRole("radio", { name: "Fast" })).toBeChecked();
      expect(
        screen.getByRole("button", { name: "Create my lesson →" }),
      ).toBeInTheDocument();
      await userEvent
        .setup()
        .click(screen.getByRole("radio", { name: "Guided" }));
      expect(
        screen.getByRole("button", { name: "Build my lesson outline →" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Create my lesson →" }),
      ).not.toBeInTheDocument();
    });

    it("shows quality and speed as a visible step, keeping technical settings collapsed", async () => {
      mount(new MemoryStandaloneBackend());
      expect(
        screen.getByRole("heading", { name: /How much quality do you need/ }),
      ).toBeVisible();
      expect(screen.getByRole("radio", { name: "Pro" })).toBeVisible();
      expect(
        screen.getByText("Technical settings").closest("details"),
      ).not.toHaveAttribute("open");
    });

    it("goes from details to a watchable video without any review stop", async () => {
      const backend = new MemoryStandaloneBackend();
      mount(backend);
      const user = await fillLesson();
      await user.click(screen.getByRole("radio", { name: "Automatic" }));
      await user.click(
        screen.getByRole("button", { name: "Create my lesson →" }),
      );
      expect(
        await screen.findByText("Your lesson video is ready to watch."),
      ).toBeVisible();
      expect(backend.planned).toHaveLength(1);
      expect(backend.stages).toEqual([
        "approve",
        "storyboard",
        "speech",
        "animation",
      ]);
      expect(screen.queryByText("Review your lesson outline")).toBeNull();
      expect(
        screen.getByRole("button", { name: "Edit video" }),
      ).toBeInTheDocument();
    });

    it.each(["Automatic", "Guided"])(
      "stops an infeasible %s lesson at outline review without starting media",
      async (flow) => {
        const backend = new MemoryStandaloneBackend();
        backend.infeasiblePlan = true;
        mount(backend);
        const user = await fillLesson();
        await user.click(screen.getByRole("radio", { name: flow }));
        await user.click(
          screen.getByRole("button", {
            name:
              flow === "Automatic"
                ? "Create my lesson →"
                : "Build my lesson outline →",
          }),
        );
        expect(
          await screen.findByRole("heading", {
            name: /won’t fit in \d+ minutes/,
          }),
        ).toBeVisible();
        expect(screen.getByText(/It needs about/)).toBeVisible();
        expect(backend.planned).toHaveLength(1);
        expect(backend.stages).toEqual([]);
        expect(backend.value!.approved).toBe(false);
        expect(backend.value!.content.minutes).toBe(
          backend.created[0]!.minutes,
        );
        expect(
          screen.getByRole("button", { name: "Create video →" }),
        ).toBeDisabled();
        expect(
          screen.getByRole("button", { name: "Review script first" }),
        ).toBeDisabled();
        await user.click(screen.getByRole("button", { name: "Script" }));
        expect(
          screen.getByRole("button", { name: "Prepare script for review" }),
        ).toBeDisabled();
        // The way out stays in view on every tab, not just the outline.
        expect(
          screen.getByRole("heading", { name: /won’t fit in \d+ minutes/ }),
        ).toBeVisible();
      },
    );

    describe("fixing a lesson that does not fit its time", () => {
      async function infeasibleLesson() {
        const backend = new MemoryStandaloneBackend();
        backend.infeasiblePlan = true;
        mount(backend);
        const user = await fillLesson();
        await user.click(screen.getByRole("radio", { name: "Guided" }));
        await user.click(
          screen.getByRole("button", { name: "Build my lesson outline →" }),
        );
        await screen.findByRole("heading", { name: /won’t fit in/ });
        return { backend, user };
      }

      it("lengthens the lesson and rebuilds the outline in one click", async () => {
        const { backend, user } = await infeasibleLesson();
        const minutes = backend.value!.content.minutes;
        backend.infeasiblePlan = false;
        await user.click(
          screen.getByRole("button", {
            name: `Make it ${minutes + 1} minutes`,
          }),
        );
        await waitFor(() =>
          expect(
            screen.queryByRole("heading", { name: /won’t fit in/ }),
          ).toBeNull(),
        );
        expect(backend.value!.content.minutes).toBe(minutes + 1);
        expect(backend.planned).toHaveLength(2);
        expect(
          await screen.findByRole("button", { name: "Create video →" }),
        ).toBeEnabled();
      });

      it("keeps the error visible when the outline can't be rebuilt after lengthening", async () => {
        const { backend, user } = await infeasibleLesson();
        const minutes = backend.value!.content.minutes;
        backend.failPlan = true;
        await user.click(
          screen.getByRole("button", {
            name: `Make it ${minutes + 1} minutes`,
          }),
        );
        expect(
          await screen.findByText(
            "Your lesson guide is unavailable. Please retry.",
          ),
        ).toBeVisible();
        expect(
          screen.getByRole("button", { name: "Retry lesson outline" }),
        ).toBeEnabled();
      });

      it("narrows the topic without changing the duration", async () => {
        const { backend, user } = await infeasibleLesson();
        const minutes = backend.value!.content.minutes;
        backend.infeasiblePlan = false;
        await user.click(
          screen.getByRole("button", { name: /^Trim it to \d+ minutes?$/ }),
        );
        await waitFor(() =>
          expect(
            screen.queryByRole("heading", { name: /won’t fit in/ }),
          ).toBeNull(),
        );
        expect(backend.value!.content.minutes).toBe(minutes);
        expect(backend.planned[1]!.message).toContain(
          `fits in ${minutes} minutes`,
        );
        expect(backend.planned[1]!.message).toContain(
          "Move one objective to another lesson.",
        );
      });

      it("opens the outline guide so the learner can choose what stays", async () => {
        const { user } = await infeasibleLesson();
        await user.click(screen.getByRole("button", { name: "Script" }));
        await user.click(
          screen.getByRole("button", { name: "Open the guide" }),
        );
        expect(
          await screen.findByRole("heading", { name: "Your lesson guide" }),
        ).toBeVisible();
      });
    });

    it("retries saved automatic media without planning again", async () => {
      const backend = new MemoryStandaloneBackend();
      backend.failStage = "speech";
      mount(backend);
      const user = await fillLesson();
      await user.click(
        screen.getByRole("button", { name: "Create my lesson →" }),
      );
      expect(
        await screen.findByText("Your lesson needs another try."),
      ).toBeVisible();
      const savedScript = backend.value!.content.storyboard;
      expect(savedScript).not.toBeNull();
      backend.failStage = null;
      await user.click(screen.getByRole("button", { name: "Retry" }));
      expect(
        await screen.findByText("Your lesson video is ready to watch."),
      ).toBeVisible();
      expect(backend.planned).toHaveLength(1);
      expect(backend.value!.content.storyboard).toBe(savedScript);
    });

    it("keeps the guided flow waiting for outline approval", async () => {
      const backend = new MemoryStandaloneBackend();
      mount(backend);
      const user = await fillLesson();
      await user.click(screen.getByRole("radio", { name: "Guided" }));
      await user.click(
        screen.getByRole("button", { name: "Build my lesson outline →" }),
      );
      expect(
        await screen.findByText("Review your lesson outline"),
      ).toBeVisible();
      expect(backend.stages).toEqual([]);
    });

    it("keeps finished steps, offers a retry, and can fall back to step-by-step review", async () => {
      const backend = new MemoryStandaloneBackend();
      backend.failStage = "speech";
      mount(backend);
      const user = await fillLesson();
      await user.click(screen.getByRole("radio", { name: "Automatic" }));
      await user.click(
        screen.getByRole("button", { name: "Create my lesson →" }),
      );
      expect(
        await screen.findByText("Your lesson needs another try."),
      ).toBeVisible();
      expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
      await user.click(
        screen.getByRole("button", { name: "Review step by step instead" }),
      );
      expect(await screen.findByText("YOUR LESSON STUDIO")).toBeVisible();
    });
  });

  it("opens the studio in fast mode while the thumbnail and outline are still pending", async () => {
    const backend = new MemoryStandaloneBackend();
    backend.thumbnailOperation = "thumbnail";
    let finish = () => {};
    backend.planGate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    mount(backend, "/lessons/new", { execute: async () => backend.get() });
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: /Fast/ }));
    await createChemistry();
    expect(await screen.findByText("YOUR LESSON STUDIO")).toBeInTheDocument();
    expect(screen.queryByLabelText("Lesson title")).not.toBeInTheDocument();
    expect(backend.planned).toHaveLength(1);
    expect(backend.planned[0].generationMode).toBe("fast");
    const thumbnail = screen.getByRole("region", { name: "Thumbnail" });
    expect(thumbnail).toHaveAttribute("aria-busy", "true");
    expect(within(thumbnail).getByRole("status")).toHaveTextContent(
      "Drawing your illustration",
    );
    const progress = screen
      .getByRole("heading", { name: "Preparing your lesson outline…" })
      .closest('[role="status"]');
    expect(progress?.querySelector(".loading-spinner")).toBeInTheDocument();
    backend.thumbnailOperation = "";
    await act(async () => finish());
    expect(
      await screen.findByRole("heading", { name: "Atoms and bonds" }),
    ).toBeInTheDocument();
    expect(thumbnail).toHaveAttribute("aria-busy", "false");
    expect(progress).not.toBeInTheDocument();
  });
  it("allows outline edits during thumbnail generation without changing the content revision", async () => {
    const backend = new MemoryStandaloneBackend();
    await backend.create({
      title: "Chemical bonds",
      description: "Explain bonding",
      minutes: 3,
    });
    await backend.plan({
      id: "lesson_one",
      expectedRevision: 0,
      message: "Plan",
    });
    let finish = () => {};
    const pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const thumbnails = new GenerateThumbnail({
      async generate() {
        await pending;
        const old = await backend.get();
        backend.value = {
          ...old,
          content: {
            ...old.content,
            image: "data:image/svg+xml;base64,PHN2Zy8+",
          },
        };
        return backend.value;
      },
    });
    const user = userEvent.setup();
    mount(backend, "/lessons/lesson_one", thumbnails);
    await user.click(
      await screen.findByRole("button", { name: "Edit outline" }),
    );
    expect(
      screen.getByRole("button", { name: "Generate thumbnail" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Cancel edits" }));
    await user.click(
      screen.getByRole("button", { name: "Generate thumbnail" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Edit outline" }),
      ).toBeEnabled(),
    );
    await act(async () => finish());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Edit outline" }),
      ).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    await user.type(screen.getByLabelText("Beat 1: Title"), " with water");
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    await screen.findByRole("heading", { name: "Atoms and bonds with water" });
    expect(backend.savedOutlines[0].expectedRevision).toBe(1);
    expect(backend.planned).toHaveLength(1);
  });
  it("edits objectives, facts and examples and adds, reorders and removes teaching beats", async () => {
    const backend = new MemoryStandaloneBackend();
    mount(backend);
    const user = await createChemistry();
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    await user.clear(screen.getByLabelText(/^Learning objectives/));
    await user.type(
      screen.getByLabelText(/^Learning objectives/),
      "Explain water molecules",
    );
    await user.click(screen.getByRole("button", { name: "Add teaching beat" }));
    await user.click(screen.getAllByText("Check your understanding")[1]);
    for (const [label, value] of [
      ["Title", "Water molecules"],
      ["Purpose", "Explain sharing"],
      ["Teaching notes", "Show two hydrogen atoms with one oxygen"],
      ["Check question", "Which atoms?"],
      ["Expected answer", "Hydrogen and oxygen"],
    ])
      await user.type(screen.getByLabelText(`Beat 2: ${label}`), value);
    screen.getByRole("button", { name: "Reorder chapter 2" }).focus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getByLabelText("Beat 1: Title")).toHaveValue(
      "Water molecules",
    );
    await user.click(screen.getByRole("button", { name: "Remove beat 2" }));
    await user.clear(screen.getByLabelText("Beat 1: Seconds"));
    await user.type(screen.getByLabelText("Beat 1: Seconds"), "180");
    await user.click(
      screen.getByRole("button", { name: "Add worked example" }),
    );
    await user.type(screen.getByLabelText("Example 2: Problem"), "Build water");
    await user.type(
      screen.getByLabelText(/^Example 2: Steps/),
      "Find oxygen\nAdd two hydrogens",
    );
    await user.type(
      screen.getByLabelText("Example 2: Result"),
      "One water molecule",
    );
    await user.click(screen.getByRole("button", { name: "Remove example 1" }));
    await user.click(screen.getByText("Facts, scope & research sources"));
    await user.clear(screen.getByLabelText(/^Required facts/));
    await user.type(
      screen.getByLabelText(/^Required facts/),
      "  Water contains hydrogen\nWater contains oxygen  ",
    );
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    await screen.findByRole("heading", { name: "Water molecules" });
    expect(backend.savedOutlines[0].outline).toMatchObject({
      objectives: ["Explain water molecules"],
      requiredFacts: ["  Water contains hydrogen", "Water contains oxygen  "],
      examples: [
        {
          problem: "Build water",
          steps: ["Find oxygen", "Add two hydrogens"],
          result: "One water molecule",
        },
      ],
    });
    expect(backend.savedOutlines[0].outline.beats).toHaveLength(1);
    expect(backend.planned).toHaveLength(1);
  }, 15000);
  it("preserves chapter order after keyboard reordering, saving and reopening", async () => {
    const backend = new MemoryStandaloneBackend();
    const view = mount(backend);
    const user = await createChemistry();
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    await user.clear(screen.getByLabelText("Beat 1: Seconds"));
    await user.type(screen.getByLabelText("Beat 1: Seconds"), "150");
    await user.click(screen.getByRole("button", { name: "Add teaching beat" }));
    await user.click(screen.getAllByText("Check your understanding")[1]);
    for (const [label, value] of [
      ["Title", "Apply the idea"],
      ["Purpose", "Practice"],
      ["Teaching notes", "Show a worked example"],
      ["Check question", "What changed?"],
      ["Expected answer", "The bonds"],
    ])
      await user.type(screen.getByLabelText(`Beat 2: ${label}`), value);
    const handle = screen.getByRole("button", { name: "Reorder chapter 2" });
    handle.focus();
    await user.keyboard(" ");
    expect(handle).toHaveAttribute("aria-pressed", "true");
    await user.keyboard("{Escape}");
    expect(handle).not.toHaveAttribute("aria-pressed", "true");
    expect(handle.closest("li")).not.toHaveClass("is-dragging");
    expect(screen.getByLabelText("Beat 1: Title")).toHaveValue(
      "Atoms and bonds",
    );
    await user.keyboard("{ArrowUp}");
    expect(handle).toHaveFocus();
    expect(screen.getByLabelText("Beat 1: Title")).toHaveValue(
      "Apply the idea",
    );
    await user.keyboard("{ArrowUp}");
    expect(screen.getByLabelText("Beat 1: Title")).toHaveValue(
      "Apply the idea",
    );
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    await screen.findByRole("button", { name: "Edit outline" });
    expect(
      backend.savedOutlines[0].outline.beats.map((beat) => beat.title),
    ).toEqual(["Apply the idea", "Atoms and bonds"]);
    view.unmount();
    mount(backend, "/lessons/lesson_one");
    await screen.findByRole("heading", { name: "Apply the idea" });
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    expect(screen.getByLabelText("Beat 1: Title")).toHaveValue(
      "Apply the idea",
    );
    expect(screen.getByLabelText("Beat 2: Title")).toHaveValue(
      "Atoms and bonds",
    );
  });

  it("saves direct edits, restores them, and proceeds through the fast pipeline without replanning", async () => {
    const backend = new MemoryStandaloneBackend();
    const view = mount(backend);
    await userEvent.click(screen.getByRole("radio", { name: "Fast" }));
    const user = await createChemistry();
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    expect(screen.getByLabelText("Message your lesson guide")).toBeDisabled();
    await user.clear(screen.getByLabelText("Beat 1: Title"));
    await user.type(
      screen.getByLabelText("Beat 1: Title"),
      "Sharing electrons in water",
    );
    await user.clear(screen.getByLabelText("Beat 1: Teaching notes"));
    await user.type(
      screen.getByLabelText("Beat 1: Teaching notes"),
      "Show two hydrogen atoms sharing with oxygen.",
    );
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    await screen.findByRole("heading", { name: "Sharing electrons in water" });
    expect(backend.planned).toHaveLength(1);
    expect(backend.savedOutlines).toHaveLength(1);
    expect(backend.value?.approved).toBe(false);
    expect(
      screen.getByText("Outline saved. Your next video will use these edits."),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Animation and review engine" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByLabelText("Pre-generate visual elements"));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Animator model" }),
      "anthropic/claude-opus-5.5",
    );
    await user.click(screen.getByRole("button", { name: "Create video →" }));
    await screen.findByRole("button", { name: "Edit video" });
    expect(backend.planned).toHaveLength(1);
    expect(backend.stages).toEqual([
      "approve",
      "storyboard",
      "speech",
      "animation",
    ]);
    expect(
      backend.advanced.every((request) => request.generationMode === "fast"),
    ).toBe(true);
    expect(backend.advanced.at(-1)?.animationBackend).toBe("direct");
    expect(backend.advanced.at(-1)?.prepareElements).toBe(true);
    expect(backend.advanced.at(-1)?.animatorModel).toBe(
      "anthropic/claude-opus-5.5",
    );
    expect(backend.advanced.map((request) => request.expectedRevision)).toEqual(
      [2, 3, 4, 5],
    );
    expect(backend.value?.content.plan?.beats[0].teachingNotes).toBe(
      "Show two hydrogen atoms sharing with oxygen.",
    );
    expect(
      screen.queryByText(
        "Outline saved. Your next video will use these edits.",
      ),
    ).not.toBeInTheDocument();
    view.unmount();
    mount(backend, "/lessons/lesson_one?edit=1");
    await screen.findByRole("heading", { name: "Sharing electrons in water" });
    expect(screen.getByRole("radio", { name: "Fast" })).toBeChecked();
    expect(screen.getByLabelText("Pre-generate visual elements")).toBeChecked();
  });

  it("validates timing, preserves failed edits, retries saving, and cancels without changing the saved outline", async () => {
    const backend = new MemoryStandaloneBackend();
    mount(backend);
    const user = await createChemistry();
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    await user.clear(screen.getByLabelText("Beat 1: Seconds"));
    await user.type(screen.getByLabelText("Beat 1: Seconds"), "240");
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "within 30 seconds of 180",
    );
    expect(backend.savedOutlines).toHaveLength(0);
    await user.clear(screen.getByLabelText("Beat 1: Seconds"));
    await user.type(screen.getByLabelText("Beat 1: Seconds"), "180");
    await user.clear(screen.getByLabelText("Beat 1: Title"));
    await user.type(screen.getByLabelText("Beat 1: Title"), "   ");
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Fill in every teaching beat",
    );
    expect(backend.savedOutlines).toHaveLength(0);
    await user.clear(screen.getByLabelText("Beat 1: Title"));
    await user.type(screen.getByLabelText("Beat 1: Title"), "Edited title");
    backend.failOutline = true;
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not save outline",
    );
    expect(screen.getByLabelText("Beat 1: Title")).toHaveValue("Edited title");
    backend.failOutline = false;
    await user.click(screen.getByRole("button", { name: "Save outline" }));
    await screen.findByRole("heading", { name: "Edited title" });
    await user.click(screen.getByRole("button", { name: "Edit outline" }));
    await user.type(screen.getByLabelText("Beat 1: Title"), " unsaved");
    await user.click(screen.getByRole("button", { name: "Cancel edits" }));
    expect(screen.getByRole("heading", { name: "Edited title" })).toBeVisible();
    expect(backend.savedOutlines).toHaveLength(1);
    expect(backend.planned).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Create video →" }));
    await screen.findByRole("button", { name: "Edit video" });
    expect(
      screen.queryByText(
        "Outline saved. Your next video will use these edits.",
      ),
    ).not.toBeInTheDocument();
  });
  it.each([false, true])(
    "shows a sent message before the guide replies and handles failure=%s",
    async (fail) => {
      const backend = new MemoryStandaloneBackend();
      await backend.create({
        title: "Chemical bonds",
        description: "Explain bonding",
        minutes: 3,
      });
      await backend.plan({
        id: "lesson_one",
        expectedRevision: 0,
        message: "Explain bonding",
      });
      let release = () => {};
      backend.planGate = new Promise<void>((resolve) => {
        release = resolve;
      });
      backend.failPlan = fail;
      mount(backend, "/lessons/lesson_one");
      const composer = await screen.findByLabelText(
        "Message your lesson guide",
      );
      const user = userEvent.setup();
      await user.type(composer, "Add a water example");
      await user.click(screen.getByRole("button", { name: "Send message ↑" }));
      expect(composer).toHaveValue("");
      expect(composer).toBeDisabled();
      const conversation = screen.getByRole("log", {
        name: "Lesson conversation",
      });
      expect(
        within(conversation).getAllByText("Add a water example"),
      ).toHaveLength(1);
      const thinking = within(conversation).getByRole("status", {
        name: "Lesson guide is thinking",
      });
      expect(thinking.querySelectorAll(".thinking-dots > span")).toHaveLength(
        3,
      );
      expect(backend.planned).toHaveLength(2);
      await act(async () => release());
      await waitFor(() => expect(thinking).not.toBeInTheDocument());
      expect(composer).toBeEnabled();
      if (fail) {
        expect(composer).toHaveValue("Add a water example");
        expect(
          within(conversation).queryByText("Add a water example"),
        ).not.toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent("unavailable");
      } else {
        expect(composer).toHaveValue("");
        expect(
          within(conversation).getAllByText("Add a water example"),
        ).toHaveLength(1);
        expect(
          within(conversation).getByText(
            "Use water to illustrate shared electrons.",
          ),
        ).toBeInTheDocument();
      }
    },
  );
  it("shows saved stages, preserves a script after failure, and retries video generation", async () => {
    const backend = new MemoryStandaloneBackend();
    let releaseGeneration = () => {};
    backend.advanceGate = new Promise<void>((resolve) => {
      releaseGeneration = resolve;
    });
    backend.failStage = "speech";
    mount(backend);
    const user = await createChemistry();
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    await user.click(screen.getByRole("button", { name: "Create video →" }));
    expect(
      await screen.findByRole("heading", {
        name: "Creating your lesson video",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Back to review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("Video generation progress"),
    ).toHaveTextContent("Script");
    await act(async () => releaseGeneration());
    await screen.findByRole("alert");
    expect(backend.value?.content.storyboard).not.toBeNull();
    expect(
      screen.getByLabelText("Video generation progress"),
    ).toHaveTextContent("Saved");
    expect(
      screen.getByLabelText("Video generation progress"),
    ).toHaveTextContent("Interrupted");
    backend.failStage = null;
    backend.advanceGate = null;
    await user.click(
      screen.getByRole("button", { name: "Retry video generation" }),
    );
    expect(
      await screen.findByRole("button", { name: "Edit video" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Video generation progress"),
    ).not.toBeInTheDocument();
    expect(backend.planned).toHaveLength(1);
  });
  it("restores a saved draft and retries real outline generation after failure", async () => {
    const backend = new MemoryStandaloneBackend();
    let releasePlan = () => {};
    backend.planGate = new Promise<void>((resolve) => {
      releasePlan = resolve;
    });
    backend.failPlan = true;
    mount(backend);
    const user = await createChemistry();
    expect(
      await screen.findByRole("heading", {
        name: "Preparing your lesson outline…",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Research and outline generation are in progress/),
    ).toBeInTheDocument();
    await act(async () => releasePlan());
    await screen.findByRole("alert");
    backend.failPlan = false;
    backend.planGate = null;
    await user.click(
      screen.getByRole("button", { name: "Retry lesson outline" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Atoms and bonds" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Preparing your lesson outline…" }),
    ).not.toBeInTheDocument();
    expect(backend.created).toHaveLength(1);
    expect(backend.planned).toHaveLength(2);
  });
  it("creates a three-minute lesson once in StrictMode, refines it, generates and restores it", async () => {
    const backend = new MemoryStandaloneBackend();
    const first = mount(backend);
    await userEvent.click(screen.getByRole("radio", { name: "Pro" }));
    const user = await createChemistry();
    expect(
      await screen.findByRole("heading", { name: "Atoms and bonds" }),
    ).toBeInTheDocument();
    expect(backend.created).toEqual([
      {
        flow: "guided",
        title: "Chemical bonds",
        description: "Explain bonding for beginners",
        minutes: 3,
        style: {
          description: "",
          audience: "",
          voiceId: "",
          visualStyleId: "flat-vector-science",
          reviewOutput: true,
          accent: "American",
          tone: "",
          pacing: "",
        },
        generationMode: "pro",
      },
    ]);
    expect(first.courses.created).toHaveLength(0);
    expect(backend.planned).toHaveLength(1);
    expect(backend.planned[0].generationMode).toBe("pro");
    await user.type(
      screen.getByLabelText("Message your lesson guide"),
      "Add a water example",
    );
    expect(
      screen.getByRole("button", { name: "Create video →" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Send message ↑" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Message your lesson guide")).toHaveValue(
        "",
      ),
    );
    expect(backend.planned[1]).toMatchObject({
      expectedRevision: 1,
      message: "Add a water example",
    });
    expect(
      screen.getAllByText("Use water to illustrate shared electrons.").length,
    ).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Create video →" }));
    expect(
      await screen.findByRole("button", { name: "Edit video" }),
    ).toBeInTheDocument();
    expect(
      backend.advanced.every((request) => request.generationMode === "pro"),
    ).toBe(true);
    expect(backend.stages).toEqual([
      "approve",
      "storyboard",
      "speech",
      "animation",
    ]);
    first.unmount();
    mount(backend, "/lessons/lesson_one");
    await user.click(await screen.findByRole("button", { name: "Edit video" }));
    await user.click(screen.getByRole("link", { name: "2 Review" }));
    expect(await screen.findByText("Add a water example")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Pro" })).toBeChecked();
    expect(backend.planned).toHaveLength(2);
  });
  it("caps the picker at ten minutes and supports keyboard changes", async () => {
    mount(new MemoryStandaloneBackend());
    const slider = screen.getByRole("slider", { name: "Duration in minutes" });
    expect(slider).toHaveAttribute("min", "1");
    expect(slider).toHaveAttribute("max", "10");
    await userEvent.click(screen.getByRole("button", { name: "10 min" }));
    expect(slider).toHaveValue("10");
    expect(screen.getByRole("button", { name: "10 min" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
  it("recovers planning errors on the saved lesson and preserves messages on errors", async () => {
    const backend = new MemoryStandaloneBackend();
    backend.failPlan = true;
    mount(backend);
    const user = await createChemistry();
    expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
    backend.failPlan = false;
    await user.click(
      screen.getByRole("button", {
        name: /Generate lesson outline|Retry lesson outline/,
      }),
    );
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    backend.failPlan = true;
    await user.type(
      screen.getByLabelText("Message your lesson guide"),
      "Use water",
    );
    await user.click(screen.getByRole("button", { name: "Send message ↑" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Message your lesson guide")).toHaveValue(
      "Use water",
    );
    expect(backend.created).toHaveLength(1);
  });
  it("keeps the script after a narration failure and resumes generation", async () => {
    const backend = new MemoryStandaloneBackend();
    backend.failStage = "speech";
    mount(backend);
    const user = await createChemistry();
    await screen.findByRole("heading", { name: "Atoms and bonds" });
    await user.click(screen.getByRole("button", { name: "Create video →" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your script is saved",
    );
    expect(
      screen.getByLabelText("Video generation progress"),
    ).toHaveTextContent(/Script.*Saved/);
    backend.failStage = null;
    await user.click(
      screen.getByRole("button", {
        name: /Continue video generation|Retry video generation/,
      }),
    );
    expect(
      await screen.findByRole("button", { name: "Edit video" }),
    ).toBeInTheDocument();
    expect(backend.planned).toHaveLength(1);
    expect(backend.created).toHaveLength(1);
  });

  it("points the home page to the Explore pages", async () => {
    mount(new MemoryStandaloneBackend(), "/");
    expect(
      await screen.findByRole("link", { name: "See all courses" }),
    ).toHaveAttribute("href", "/explore");
    expect(
      screen.queryByRole("heading", { name: "Courses you might like" }),
    ).not.toBeInTheDocument();
  });
});

it.each([
  "Flat-Vector Science",
  "Watercolor Wash",
  "Tech Glow Explainer",
  "Whiteboard Explainer",
  "Halftone Pop Panel",
  "Risograph Zine",
  "Gouache Travel Poster",
  "Soft 3D Clay",
  "Memphis Group",
  "Bauhaus Poster",
  "International Typographic Style",
])(
  "saves and resumes %s lesson details without planning until continue",
  async (styleName) => {
    const backend = new MemoryStandaloneBackend();
    const user = userEvent.setup();
    const view = mount(backend);
    await user.click(
      screen.getByRole("radio", { name: new RegExp("^" + styleName) }),
    );
    await user.type(screen.getByLabelText("Lesson title"), "Rainbows");
    await user.type(
      screen.getByLabelText("What would you like to learn?"),
      "Explain colors in sunlight",
    );
    await user.click(screen.getByText("Voice & delivery preferences"));
    await user.type(
      screen.getByLabelText("Teaching tone and preferences (optional)"),
      "Playful for children",
    );
    expect(backend.created).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Save as draft" }),
      ).toBeDisabled(),
    );
    expect(backend.planned).toHaveLength(0);
    await user.type(screen.getByLabelText("Lesson title"), " in water");
    await user.clear(
      screen.getByLabelText("Teaching tone and preferences (optional)"),
    );
    await user.type(
      screen.getByLabelText("Teaching tone and preferences (optional)"),
      "Warm and reassuring",
    );
    expect(screen.getByRole("button", { name: "Save as draft" })).toBeEnabled();
    expect(backend.value?.content.title).toBe("Rainbows");
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(() =>
      expect(backend.value?.content.title).toBe("Rainbows in water"),
    );
    expect(backend.created).toHaveLength(1);
    view.unmount();
    mount(backend, "/workspace");
    await user.click(
      await screen.findByRole("link", { name: "Continue lesson" }),
    );
    expect(await screen.findByLabelText("Lesson title")).toHaveValue(
      "Rainbows in water",
    );
    expect(
      screen.getByLabelText("Teaching tone and preferences (optional)"),
    ).toHaveValue("Warm and reassuring");
    expect(
      screen.getByRole("radio", { name: new RegExp("^" + styleName) }),
    ).toBeChecked();
    expect(backend.value?.content.style?.visualStyleId).toBe(
      {
        "Flat-Vector Science": "flat-vector-science",
        "Watercolor Wash": "watercolor-wash",
        "Tech Glow Explainer": "tech-glow",
        "Whiteboard Explainer": "whiteboard",
        "Halftone Pop Panel": "halftone-pop",
        "Risograph Zine": "risograph",
        "Gouache Travel Poster": "gouache-poster",
        "Soft 3D Clay": "soft-3d",
        "Memphis Group": "memphis",
        "Bauhaus Poster": "bauhaus",
        "International Typographic Style": "swiss-grid",
      }[styleName],
    );
    expect(backend.planned).toHaveLength(0);
    await user.click(screen.getByRole("radio", { name: "Guided" }));
    await user.click(
      screen.getByRole("button", { name: "Build my lesson outline →" }),
    );
    await waitFor(() => expect(backend.planned).toHaveLength(1));
    expect(backend.created).toHaveLength(1);
  },
);

it("filters finished lessons by status, type, and search and resumes without generation", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({
    title: "Chemical bonds",
    description: "Explain bonding",
    minutes: 3,
  });
  let lesson = await backend.plan({
    id: created.id,
    expectedRevision: 0,
    message: created.description,
  });
  for (const stage of [
    "approve",
    "storyboard",
    "speech",
    "animation",
  ] as const) {
    lesson = await backend.advance({
      id: lesson.id,
      expectedRevision: lesson.revision,
      stage,
    });
  }
  const user = userEvent.setup();
  mount(backend, "/workspace?status=finished&type=lesson&search=Chemical");
  expect(
    await screen.findByRole("heading", { name: "Chemical bonds" }),
  ).toBeVisible();
  expect(screen.getByText("Video ready")).toBeVisible();
  expect(
    screen.queryByRole("link", { name: "Continue lesson" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /^Drafts/ }));
  expect(
    await screen.findByText("No work matches these filters"),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: /^Finished/ }));
  await user.click(screen.getByRole("link", { name: "Open lesson" }));
  expect(
    await screen.findByRole("heading", { name: "Chemical bonds" }),
  ).toBeVisible();
  expect(backend.planned).toHaveLength(1);
  expect(backend.stages).toHaveLength(4);
});

it("keeps unsaved lesson edits after a failed save and supports retry", async () => {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Rainbows",
    description: "Explain sunlight",
    minutes: 1,
  });
  const user = userEvent.setup();
  mount(backend, "/lessons/lesson_one/edit");
  await user.type(await screen.findByLabelText("Lesson title"), " and color");
  await user.click(screen.getByRole("radio", { name: /^Flat-Vector Science/ }));
  backend.failUpdate = true;
  await user.click(screen.getByRole("button", { name: "Save as draft" }));
  expect(
    await screen.findByText("Could not save draft. Try again."),
  ).toBeVisible();
  expect(screen.getByLabelText("Lesson title")).toHaveValue(
    "Rainbows and color",
  );
  expect(backend.value?.content.title).toBe("Rainbows");
  backend.failUpdate = false;
  await user.click(screen.getByRole("button", { name: "Save as draft" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Save as draft" }),
    ).toBeDisabled(),
  );
  expect(backend.value?.content.title).toBe("Rainbows and color");
  expect(backend.created).toHaveLength(1);
});

it("restores an active outline after a fresh mount and polls for its saved result", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({
    title: "Bonds",
    description: "Explain bonds",
    minutes: 1,
  });
  backend.value = { ...created, activeOperation: "plan" };
  const mounted = mount(backend, "/lessons/lesson_one");
  expect(await screen.findByText(/Preparing outline/)).toBeInTheDocument();
  expect(
    screen.queryByRole("button", {
      name: /Generate lesson outline|Retry lesson outline/,
    }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Message your lesson guide")).toBeDisabled();
  expect(backend.planned).toHaveLength(0);
  mounted.unmount();
  mount(backend, "/lessons/lesson_one");
  expect(await screen.findByText(/Preparing outline/)).toBeInTheDocument();
  await backend.plan({
    id: created.id,
    expectedRevision: created.revision,
    message: "Plan",
  });
  backend.value = { ...backend.value!, activeOperation: "" };
  await waitFor(
    () =>
      expect(
        screen.getByRole("button", { name: "Edit outline" }),
      ).toBeEnabled(),
    { timeout: 4500 },
  );
});

it("restores video progress with conflicting controls disabled and observes completion", async () => {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Bonds",
    description: "Explain bonds",
    minutes: 1,
  });
  const planned = await backend.plan({
    id: "lesson_one",
    expectedRevision: 0,
    message: "Plan",
  });
  backend.value = { ...planned, activeOperation: "video" };
  mount(backend, "/lessons/lesson_one");
  expect(
    await screen.findByRole("heading", { name: "Creating your lesson video" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Create video|Creating video/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Edit outline" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByLabelText("Message your lesson guide"),
  ).not.toBeInTheDocument();
  expect(backend.stages).toHaveLength(0);
  await backend.advance({
    id: planned.id,
    expectedRevision: planned.revision,
    stage: "video",
    generationMode: "fast",
  });
  backend.value = { ...backend.value!, activeOperation: "" };
  await waitFor(
    () =>
      expect(
        screen.getByRole("button", { name: "Edit video" }),
      ).toBeInTheDocument(),
    { timeout: 4500 },
  );
  expect(
    screen.queryByRole("heading", { name: "Creating your lesson video" }),
  ).not.toBeInTheDocument();
});

it("shows a saved generation failure after refresh and allows a retry", async () => {
  const backend = new MemoryStandaloneBackend();
  const draft = await backend.create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
  });
  backend.value = {
    ...draft,
    operationError:
      "The previous step failed. Completed work is saved. Please try again.",
  };
  mount(backend, "/lessons/lesson_one");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The previous step failed",
  );
  expect(
    screen.getByRole("button", {
      name: /Generate lesson outline|Retry lesson outline/,
    }),
  ).toBeEnabled();
});

it("resumes a refreshed draft with the revision saved by its completed thumbnail step", async () => {
  const backend = new MemoryStandaloneBackend();
  const draft = await backend.create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
    style: {
      description: "",
      audience: "",
      voiceId: "",
      visualStyleId: "flat-vector-science",
      reviewOutput: true,
    },
  });
  backend.value = { ...draft, activeOperation: "thumbnail" };
  mount(backend, "/lessons/lesson_one/edit");
  expect(
    await screen.findByText(/In Progress — Drawing your thumbnail/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Saving your lesson…" }),
  ).toBeDisabled();
  backend.value = {
    ...draft,
    revision: 1,
    activeOperation: "",
    content: { ...draft.content, image: "saved-thumbnail" },
  };
  await waitFor(
    () =>
      expect(
        screen.getByRole("button", { name: "Build my lesson outline →" }),
      ).toBeEnabled(),
    { timeout: 4500 },
  );
  await userEvent
    .setup()
    .click(screen.getByRole("radio", { name: /^Flat-Vector Science/ }));
  await userEvent.setup().click(screen.getByRole("radio", { name: "Guided" }));
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Build my lesson outline →" }));
  await screen.findByRole("heading", { name: "Atoms and bonds" });
  expect(backend.planned[0].expectedRevision).toBe(1);
});

it("surfaces failed status polling instead of leaving stale progress on screen, and recovers", async () => {
  const backend = new MemoryStandaloneBackend();
  const draft = await backend.create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
  });
  backend.value = { ...draft, activeOperation: "plan" };
  mount(backend, "/lessons/lesson_one");
  await screen.findByText(/Preparing outline/);
  backend.failGet = true;
  await waitFor(
    () =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Could not verify lesson status",
      ),
    { timeout: 4500 },
  );
  expect(screen.getByText(/Preparing outline/)).not.toBeVisible();
  expect(
    screen.queryByRole("button", {
      name: /Generate lesson outline|Retry lesson outline/,
    }),
  ).not.toBeInTheDocument();
  backend.failGet = false;
  backend.value = { ...draft, activeOperation: "" };
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByRole("button", {
      name: /Generate lesson outline|Retry lesson outline/,
    }),
  ).toBeEnabled();
});

it("preserves an unsent message when background status polling fails", async () => {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
  });
  await backend.plan({
    id: "lesson_one",
    expectedRevision: 0,
    message: "Plan",
  });
  mount(backend, "/lessons/lesson_one");
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText("Message your lesson guide"),
    "Keep my water example",
  );
  backend.failGet = true;
  await waitFor(
    () =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Could not verify lesson status",
      ),
    { timeout: 4500 },
  );
  expect(
    screen.queryByRole("button", { name: "Send message ↑" }),
  ).not.toBeInTheDocument();
  backend.failGet = false;
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByLabelText("Message your lesson guide")).toHaveValue(
    "Keep my water example",
  );
  expect(backend.planned).toHaveLength(1);
});

it("opens finished lessons for learners and restores the complete studio only through Edit", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({
    title: "Heel striking",
    description: "Running mechanics",
    minutes: 1,
  });
  const planned = await backend.plan({
    id: created.id,
    expectedRevision: 0,
    message: "Explain running mechanics",
  });
  backend.value = {
    ...planned,
    content: {
      ...planned.content,
      videoUrl: "/test-media/heel.mp4",
      style: {
        ...styleFixture({
          description: "Sports science",
          audience: "College athletes",
          voiceId: "",
        }),
      },
    },
  };
  const user = userEvent.setup();
  const view = mount(backend, "/lessons/lesson_one");
  const edit = await screen.findByRole("button", { name: "Edit video" });
  expect(screen.queryByText("Running mechanics")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Heel striking video")).toHaveAttribute(
    "src",
    "/test-media/heel.mp4",
  );
  expect(
    screen.queryByLabelText("Message your lesson guide"),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("radio", { name: "Pro" })).not.toBeInTheDocument();
  await user.click(edit);
  expect(
    screen.getByRole("navigation", { name: "What would you like to change?" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "2 Review" }));
  expect(
    screen.getByLabelText("Message your lesson guide"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("region", { name: "Lesson outline" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "Pro" })).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Regenerate video" }),
  ).toBeEnabled();
  expect(
    screen.queryByLabelText("Regenerate video from"),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Done editing" }));
  expect(
    screen.queryByLabelText("Message your lesson guide"),
  ).not.toBeInTheDocument();
  view.unmount();
  mount(backend, "/lessons/lesson_one?edit=1&step=review");
  expect(
    await screen.findByLabelText("Message your lesson guide"),
  ).toBeInTheDocument();
  expect(backend.planned).toHaveLength(1);
  expect(backend.advanced).toHaveLength(0);
});

it("plays saved animation source through the authenticated playback endpoint", async () => {
  const backend = new MemoryStandaloneBackend();
  const value = await backend.create({
    title: "Heel striking",
    description: "Running mechanics",
    minutes: 1,
  });
  backend.value = {
    ...value,
    content: {
      ...value.content,
      animation: { status: "animation_ready", projectKey: "saved/remotion" },
    },
  };
  mount(backend, "/lessons/lesson_one");
  await screen.findByRole("button", { name: "Edit video" });
  expect(screen.getByLabelText("Heel striking video")).toHaveAttribute(
    "src",
    "/api/v1/lessons/lesson_one/video?v=saved%2Fremotion",
  );
  expect(backend.advanced).toHaveLength(0);
});

it.each(["guided", "automatic"] as const)(
  "plays reviewed code before rendering finishes in the %s flow",
  async (flow) => {
    const stage = "render";
    const backend = new MemoryStandaloneBackend();
    const value = await backend.create({
      title: "Moon phases",
      description: "Explain the Moon",
      minutes: 1,
    });
    const total = {
      knownUsd: "0.12",
      calls: 1,
      pendingCalls: 0,
      estimatedCalls: 0,
      inputTokens: 10,
      outputTokens: 20,
    };
    backend.value = {
      ...value,
      flow,
      activeOperation: "video",
      spend: {
        currency: "USD",
        total,
        shared: total,
        lessons: [{ lessonId: value.id, total }],
        breakdown: [
          {
            lessonId: value.id,
            stage,
            provider: "openrouter",
            model: "test-model",
            total,
          },
        ],
        steps: [
          {
            id: "step",
            lessonId: value.id,
            stage,
            backend: "direct",
            startedAt: Date.now() / 1000,
            finishedAt: null,
          },
        ],
      },
    };
    const { client } = mount(backend, "/lessons/lesson_one");
    await screen.findByRole("heading", { name: "Moon phases" });
    expect(screen.queryByText("Lesson AI spend")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("table", { name: "AI spend by step" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Moon phases video"),
    ).not.toBeInTheDocument();

    const source = {
      ...backend.value,
      content: {
        ...value.content,
        animation: {
          status: "animation_ready",
          projectKey: "saved/javascript",
          outputHash: "draft",
          reviewStatus: "pending",
        },
      },
    };
    await act(async () => {
      backend.value = source;
      client.setQueryData(["lessons", value.id], source);
    });
    const video = await screen.findByLabelText("Moon phases video");
    expect(video).toBeVisible();
    expect(screen.getByText("Your video is ready to watch")).toBeVisible();
    expect(
      screen.queryByText(
        "Watch animation preview · video processing incomplete",
      ),
    ).not.toBeInTheDocument();

    await act(async () => {
      backend.value = {
        ...source,
        activeOperation: "",
        content: {
          ...source.content,
          animation: { ...source.content.animation, reviewStatus: "approved" },
        },
      };
      client.setQueryData(["lessons", value.id], backend.value);
    });
    expect(screen.getByLabelText("Moon phases video")).toBe(video);
    expect(backend.advanced).toHaveLength(0);
  },
);

it("shows a saved interactive in learner and edit views without generation controls", async () => {
  const backend = new MemoryStandaloneBackend();
  const value = await backend.create({
    title: "Pendulum",
    description: "Explore a swing",
    minutes: 1,
  });
  backend.value = {
    ...value,
    content: {
      ...value.content,
      videoUrl: "/test-media/swing.mp4",
      interactive: {
        planHash: "saved",
        reason: "Explore the effect of gravity",
        html: "<!doctype html><html><body><button>Reset experiment</button></body></html>",
        spec: {
          kind: "custom",
          title: "Explore a pendulum",
          objective: "Compare gravity settings",
          explanation: "Try changing gravity",
          controls: ["Gravity"],
          behavior: "Swing",
          prompts: ["What changes?"],
          acceptanceCriteria: ["Controls work"],
          initialLength: 1,
          initialGravity: 9.81,
          initialAngle: 15,
        },
      },
    },
  };
  const user = userEvent.setup();
  mount(backend, "/lessons/lesson_one");
  await screen.findByRole("button", { name: "Edit video" });
  const frame = screen.getByTitle("Explore a pendulum");
  expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  expect(screen.queryByText("Why this activity?")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Edit video" }));
  expect(screen.getByTitle("Explore a pendulum")).toBe(frame);
  expect(screen.getByText("Why this activity?")).toBeInTheDocument();
  expect(backend.advanced).toHaveLength(0);
});

it("can reopen the studio after browser Back during an outline edit", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({
    title: "Heel striking",
    description: "Running mechanics",
    minutes: 1,
  });
  const planned = await backend.plan({
    id: created.id,
    expectedRevision: 0,
    message: "Explain running mechanics",
  });
  backend.value = {
    ...planned,
    content: { ...planned.content, videoUrl: "/test-media/heel.mp4" },
  };
  const user = userEvent.setup();
  mount(backend, "/lessons/lesson_one", undefined, true);
  await user.click(await screen.findByRole("button", { name: "Edit video" }));
  await user.click(screen.getByRole("button", { name: "Outline" }));
  await user.click(screen.getByRole("button", { name: "Edit outline" }));
  await user.type(screen.getByLabelText("Beat 1: Title"), " unsaved");
  expect(screen.getByRole("button", { name: "Done editing" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Go back in history" }));
  expect(screen.getByLabelText("Beat 1: Title")).toHaveValue(
    "Atoms and bonds unsaved",
  );
  expect(
    screen.getByRole("form", { name: "Edit lesson outline" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cancel edits" }));
  expect(screen.getByRole("button", { name: "Done editing" })).toBeEnabled();
});

it("keeps an unsaved review script when browser Back returns to the video step", async () => {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Rain",
    description: "Explain rain",
    minutes: 1,
  });
  const planned = await backend.plan({ id: "lesson_one", expectedRevision: 0 });
  const scripted = await backend.advance({
    id: "lesson_one",
    expectedRevision: planned.revision,
    stage: "storyboard",
  });
  backend.value = {
    ...scripted,
    content: { ...scripted.content, videoUrl: "/rain-v1.mp4" },
  };
  mount(backend, "/lessons/lesson_one", undefined, true);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "View script" }));
  await user.click(screen.getByRole("button", { name: "Edit script" }));
  await user.type(
    screen.getByLabelText("Narration for scene 1"),
    " Keep this draft.",
  );
  await user.click(screen.getByRole("button", { name: "Go back in history" }));
  expect(screen.getByLabelText("Narration for scene 1")).toHaveValue(
    "Atoms share electrons. Keep this draft.",
  );
  await user.click(screen.getByRole("button", { name: "Save script" }));
  await waitFor(() => expect(backend.savedScripts).toHaveLength(1));
  expect(backend.savedScripts[0].narrations[0]).toBe(
    "Atoms share electrons. Keep this draft.",
  );
});

it("reviews and edits the script before generating narration or animation", async () => {
  const backend = new MemoryStandaloneBackend();
  mount(backend);
  const user = await createChemistry();
  await screen.findByRole("heading", { name: "Atoms and bonds" });
  await user.click(screen.getByRole("button", { name: "Review script first" }));
  await screen.findByRole("heading", { name: "Script & narration" });
  expect(backend.stages).toEqual(["approve", "storyboard"]);
  await user.click(screen.getByRole("button", { name: "Edit script" }));
  await user.clear(screen.getByLabelText("Narration for scene 1"));
  await user.type(
    screen.getByLabelText("Narration for scene 1"),
    "Water molecules share electrons.",
  );
  expect(screen.getByRole("button", { name: "Outline" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Save script" }));
  expect(
    await screen.findByText("Water molecules share electrons."),
  ).toBeInTheDocument();
  expect(backend.savedScripts).toHaveLength(1);
  expect(backend.stages).not.toContain("speech");
  await user.click(screen.getByRole("button", { name: "Create video →" }));
  await screen.findByRole("button", { name: "Edit video" });
  expect(backend.value?.content.storyboard?.scenes[0].narrationText).toBe(
    "Water molecules share electrons.",
  );
  expect(backend.planned).toHaveLength(1);
});

it("keeps the current video playable after a script edit and returns to the saved draft", async () => {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Rain",
    description: "Explain rain",
    minutes: 1,
  });
  const planned = await backend.plan({ id: "lesson_one", expectedRevision: 0 });
  const scripted = await backend.advance({
    id: "lesson_one",
    expectedRevision: planned.revision,
    stage: "storyboard",
  });
  backend.value = {
    ...scripted,
    content: { ...scripted.content, videoUrl: "/rain-v1.mp4" },
  };
  mount(backend, "/lessons/lesson_one");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit video" }));
  await user.click(screen.getByRole("button", { name: "Script" }));
  await user.click(screen.getByRole("button", { name: "Edit script" }));
  await user.type(
    screen.getByLabelText("Narration for scene 1"),
    " Follow a drop of water.",
  );
  await user.click(screen.getByRole("button", { name: "Save script" }));
  await screen.findByText(/Editing a new draft/);
  expect(screen.getByLabelText("Rain video")).toHaveAttribute(
    "src",
    "/rain-v1.mp4",
  );
  expect(backend.value?.content.videoUrl).toBeNull();
  expect(backend.value?.playbackContent?.videoUrl).toBe("/rain-v1.mp4");
  await user.click(screen.getByRole("button", { name: "Watch current video" }));
  expect(screen.getByLabelText("Rain video")).toHaveAttribute(
    "src",
    "/rain-v1.mp4",
  );
  await user.click(screen.getByRole("button", { name: "Continue editing" }));
  await user.click(screen.getByRole("button", { name: "Script" }));
  expect(screen.getByText(/Follow a drop of water/)).toBeInTheDocument();
});

it("retains unsaved narration after a failed save and retries without losing the text", async () => {
  const backend = new MemoryStandaloneBackend();
  mount(backend);
  const user = await createChemistry();
  await screen.findByRole("heading", { name: "Atoms and bonds" });
  await user.click(screen.getByRole("button", { name: "Review script first" }));
  await screen.findByRole("heading", { name: "Script & narration" });
  await user.click(screen.getByRole("button", { name: "Edit script" }));
  await user.type(
    screen.getByLabelText("Narration for scene 1"),
    " My saved revision.",
  );
  backend.failScript = true;
  await user.click(screen.getByRole("button", { name: "Save script" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Narration for scene 1")).toHaveValue(
    "Atoms share electrons. My saved revision.",
  );
  backend.failScript = false;
  await user.click(screen.getByRole("button", { name: "Save script" }));
  await screen.findByText("Atoms share electrons. My saved revision.");
  expect(backend.savedScripts).toHaveLength(1);
});

it("keeps pending animation previews out of the finished lesson filter", async () => {
  const backend = new MemoryStandaloneBackend();
  await backend.create({
    title: "Rain preview",
    description: "Explain rain",
    minutes: 1,
  });
  backend.value = {
    ...backend.value!,
    content: {
      ...backend.value!.content,
      animation: {
        status: "animation_ready",
        reviewStatus: "pending",
        projectKey: "saved/javascript",
      },
    },
  };
  mount(backend, "/workspace?status=finished&type=lesson");
  await screen.findByText("No work matches these filters");
  expect(
    screen.queryByRole("heading", { name: "Rain preview" }),
  ).not.toBeInTheDocument();
});

it.each(["storyboard", "script/generate", "video"])(
  "offers cancellation for a restored %s generation",
  async (operation) => {
    const backend = new MemoryStandaloneBackend();
    const draft = await backend.create({
      title: "Atoms",
      description: "Explain atoms",
      minutes: 1,
    });
    await backend.plan({ id: draft.id, expectedRevision: 0 });
    backend.value = { ...backend.value!, activeOperation: operation };
    const requests: CancelGenerationRequest[] = [];
    mount(
      backend,
      `/lessons/${draft.id}?step=review&panel=script`,
      undefined,
      false,
      {
        execute: async (request) => {
          requests.push(request);
          return true;
        },
      },
    );
    const label =
      operation === "video"
        ? "Cancel video generation"
        : "Cancel script generation";
    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: label }));
    expect(
      await screen.findByRole("button", { name: "Cancellation requested" }),
    ).toBeDisabled();
    expect(requests).toEqual([{ kind: "lesson", id: draft.id }]);
  },
);

it.each(["automatic", "cancelling/automatic"])(
  "reopens a saved automatic run with %s activity without restarting it",
  async (activeOperation) => {
    const backend = new MemoryStandaloneBackend();
    const draft = await backend.create({
      title: "Atoms",
      description: "Explain atoms",
      minutes: 1,
      flow: "automatic",
    });
    backend.value = { ...draft, activeOperation };
    mount(backend, "/lessons/lesson_one");
    expect(await screen.findByText("AUTOMATIC LESSON")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Creating your lesson" }),
    ).toBeVisible();
    expect(screen.queryByText("Saving changes")).toBeNull();
    expect(backend.planned).toHaveLength(0);
    expect(backend.stages).toHaveLength(0);
  },
);

it("consumes a create arrival during a running lesson instead of queuing a second run", async () => {
  const backend = new MemoryStandaloneBackend();
  const draft = await backend.create({
    title: "Atoms",
    description: "Explain atoms",
    minutes: 1,
    flow: "automatic",
  });
  backend.value = { ...draft, activeOperation: "automatic" };
  const { client } = mount(
    backend,
    "/lessons/lesson_one",
    undefined,
    false,
    undefined,
    { startPlanning: true },
  );
  expect(await screen.findByText("AUTOMATIC LESSON")).toBeVisible();
  backend.value = { ...draft, activeOperation: "" };
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["lessons", draft.id] });
  });
  expect(backend.planned).toHaveLength(0);
  expect(backend.stages).toHaveLength(0);
});

it.each([
  ["Lesson title", "Bonds"],
  ["What would you like to learn?", "Explain bonds"],
])("creates a lesson with only %s", async (field, value) => {
  const backend = new MemoryStandaloneBackend();
  mount(backend);
  const user = userEvent.setup();
  expect(screen.getByLabelText("Lesson title")).not.toBeRequired();
  expect(
    screen.getByLabelText("What would you like to learn?"),
  ).not.toBeRequired();
  await user.click(screen.getByRole("radio", { name: /^Flat-Vector Science/ }));
  await user.type(screen.getByLabelText(field), value);
  await user.click(screen.getByRole("radio", { name: "Guided" }));
  await user.click(
    screen.getByRole("button", { name: "Build my lesson outline →" }),
  );
  expect(await screen.findByText("YOUR LESSON STUDIO")).toBeVisible();
  expect(backend.value?.content.title).toBe(value);
  expect(backend.value?.description).toBe(value);
  expect(backend.planned).toHaveLength(1);
});

it.each([
  ["script", "From the script"],
  ["speech", "From the narration"],
  ["animation", "Animation only"],
  ["outline", "Everything"],
] as const)(
  "regenerates video from %s using the selected quality",
  async (restart, option) => {
    const backend = new MemoryStandaloneBackend();
    const created = await backend.create({ title: "Bonds", minutes: 3 });
    const planned = await backend.plan({ id: created.id, expectedRevision: 0 });
    await backend.advance({
      id: created.id,
      expectedRevision: planned.revision,
      stage: "video",
    });
    backend.advanced.length = 0;
    mount(backend, "/lessons/lesson_one?edit=1&step=video");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("radio", { name: "Pro" }));
    await user.click(screen.getByRole("button", { name: "Regenerate video" }));
    expect(
      screen.getByRole("group", { name: "Regenerate video" }),
    ).toHaveTextContent("Uses your Pro quality setting");
    await user.click(screen.getByRole("button", { name: option }));
    expect(
      screen.queryByRole("group", { name: "Regenerate video" }),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(backend.advanced.some((r) => r.stage === "animation")).toBe(true),
    );
    const animation = backend.advanced.find((r) => r.stage === "animation");
    expect(animation?.generationMode).toBe("pro");
    if (restart === "outline") {
      expect(backend.planned).toHaveLength(2);
    } else {
      expect(backend.planned).toHaveLength(1);
      expect(animation?.regenerateFrom).toBe(restart);
    }
  },
);

it("shows only the regeneration progress until the new video can play", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({ title: "Bonds", minutes: 3 });
  const planned = await backend.plan({ id: created.id, expectedRevision: 0 });
  await backend.advance({
    id: created.id,
    expectedRevision: planned.revision,
    stage: "video",
  });
  let release = () => {};
  backend.advanceGate = new Promise<void>((resolve) => {
    release = resolve;
  });
  mount(backend, "/lessons/lesson_one?edit=1&step=video");
  const user = userEvent.setup();
  expect(await screen.findByLabelText("Bonds video")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Regenerate video" }));
  await user.click(screen.getByRole("button", { name: "From the narration" }));
  const progress = await screen.findByLabelText("Video generation progress");
  expect(
    within(progress).getByRole("heading", { name: "Regenerating your video" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Regenerating video")).toBeInTheDocument();
  expect(progress).toHaveTextContent(/Script.*Kept/);
  expect(progress).toHaveTextContent(/Narration.*In progress/);
  expect(screen.queryByLabelText("Bonds video")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Outline" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText(/Editing a new draft/)).not.toBeInTheDocument();
  await act(async () => release());
  expect(await screen.findByLabelText("Bonds video")).toBeInTheDocument();
  expect(
    screen.queryByLabelText("Video generation progress"),
  ).not.toBeInTheDocument();
});

it("can regenerate an existing outline and script without generating video", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({ title: "Bonds", minutes: 3 });
  await backend.plan({ id: created.id, expectedRevision: 0 });
  mount(backend, "/lessons/lesson_one?edit=1&step=review");
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Regenerate outline" }),
  );
  await waitFor(() => expect(backend.planned).toHaveLength(2));
  await user.click(screen.getByRole("button", { name: "Script" }));
  await user.click(
    screen.getByRole("button", { name: "Prepare script for review" }),
  );
  const regenerate = await screen.findByRole("button", {
    name: "Regenerate script",
  });
  await waitFor(() => expect(regenerate).toBeEnabled());
  await user.click(regenerate);
  await waitFor(() =>
    expect(
      backend.advanced.filter((r) => r.stage === "storyboard"),
    ).toHaveLength(2),
  );
  expect(backend.advanced.at(-1)?.regenerateFrom).toBe("script");
  expect(backend.stages).not.toContain("animation");
  expect(backend.stages).not.toContain("speech");
});

it("explains what an edit rebuilds and offers only the stages that remain", async () => {
  const backend = new MemoryStandaloneBackend();
  const created = await backend.create({ title: "Bonds", minutes: 3 });
  const planned = await backend.plan({ id: created.id, expectedRevision: 0 });
  const finished = await backend.advance({
    id: created.id,
    expectedRevision: planned.revision,
    stage: "video",
  });
  await backend.saveScript({
    id: created.id,
    expectedRevision: finished.revision,
    narrations: ["Atoms share electrons."],
  });
  mount(backend, "/lessons/lesson_one?edit=1&step=review");
  const user = userEvent.setup();
  expect(
    await screen.findByText(
      "You have saved changes that aren’t in your video yet. Generating rebuilds the narration and animation and keeps everything before it.",
    ),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Generate updated video →" }),
  ).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Regenerate" }));
  expect(screen.getByRole("button", { name: "Everything" })).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "From the narration" }),
  ).toBeEnabled();
  expect(screen.getByRole("button", { name: "Animation only" })).toBeDisabled();
  await user.keyboard("{Escape}");
  expect(
    screen.queryByRole("group", { name: "Regenerate video" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Regenerate" })).toHaveFocus();
});
