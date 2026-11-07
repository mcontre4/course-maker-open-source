import { describe, expect, it } from "vitest";
import {
  briefProblem,
  changeProblem,
  detailsProblem,
  interactiveIdeas,
  interactiveLimits,
  interactiveState,
  learnerView,
  type LessonInteractive,
} from "./lesson-interactive";

const interactive = (
  over: Partial<LessonInteractive> = {},
): LessonInteractive => ({
  id: "interactive_1",
  lessonId: "lesson_1",
  brief: "A pendulum",
  title: "Pendulum lab",
  goal: "See what changes the swing",
  prompts: ["Double the length"],
  versions: [{ number: 1, request: "A pendulum", createdAt: "2026-11-01" }],
  currentVersion: 1,
  html: "<p>one</p>",
  publishedVersion: null,
  publishedHtml: null,
  build: null,
  failure: null,
  revision: 1,
  createdAt: "2026-11-01",
  updatedAt: "2026-11-01",
  ...over,
});

describe("interactiveState", () => {
  it("is a draft until it is added to the lesson", () => {
    expect(interactiveState(interactive())).toBe("draft");
  });

  it("is live when learners get the version being previewed", () => {
    expect(
      interactiveState(
        interactive({ publishedVersion: 1, publishedHtml: "<p>one</p>" }),
      ),
    ).toBe("live");
  });

  it("notices a newer version learners do not have yet", () => {
    expect(
      interactiveState(
        interactive({
          currentVersion: 2,
          publishedVersion: 1,
          publishedHtml: "<p>one</p>",
        }),
      ),
    ).toBe("live_with_changes");
  });

  it("reports building ahead of everything else", () => {
    expect(
      interactiveState(
        interactive({
          publishedVersion: 1,
          publishedHtml: "<p>one</p>",
          build: { request: "x", stage: "designing", startedAt: "now" },
        }),
      ),
    ).toBe("building");
  });

  it("counts as failed only when there is nothing to show", () => {
    const failure = { request: "x", message: "Stopped" };
    expect(interactiveState(interactive({ failure }))).toBe("draft");
    expect(
      interactiveState(
        interactive({
          failure,
          versions: [],
          currentVersion: null,
          html: null,
        }),
      ),
    ).toBe("failed");
  });
});

describe("learnerView", () => {
  it("hides interactives that are not in the lesson", () => {
    expect(learnerView(interactive())).toBeNull();
  });

  it("gives learners the published page, not the newest draft", () => {
    const view = learnerView(
      interactive({
        currentVersion: 2,
        html: "<p>two</p>",
        publishedVersion: 1,
        publishedHtml: "<p>one</p>",
      }),
    );
    expect(view).toMatchObject({ version: 1, html: "<p>one</p>" });
    expect(view).not.toHaveProperty("brief");
  });
});

describe("creator input", () => {
  it("asks for a description and a change in plain words", () => {
    expect(briefProblem("   ")).toMatch(/Describe/);
    expect(briefProblem("A pendulum")).toBeNull();
    expect(briefProblem("x".repeat(interactiveLimits.brief + 1))).toMatch(
      /under/,
    );
    expect(changeProblem("")).toMatch(/change/);
  });

  it("checks the details learners see", () => {
    const details = { title: "Lab", goal: "", prompts: ["Try it"] };
    expect(detailsProblem(details)).toBeNull();
    expect(detailsProblem({ ...details, title: " " })).toMatch(/title/);
    expect(detailsProblem({ ...details, prompts: [""] })).toMatch(/empty/);
  });
});

describe("interactiveIdeas", () => {
  it("draws on the lesson's topics", () => {
    const ideas = interactiveIdeas({
      title: "Pendulums",
      topics: ["pendulum period", "gravity"],
    });
    expect(ideas).toHaveLength(3);
    expect(ideas[0]).toContain("pendulum period");
    expect(ideas[1]).toContain("gravity");
  });

  it("offers nothing when the lesson says nothing yet", () => {
    expect(interactiveIdeas({ title: " ", topics: [] })).toEqual([]);
  });
});
