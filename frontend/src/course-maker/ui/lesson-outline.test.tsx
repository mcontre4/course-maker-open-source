import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { LessonPlanResponse } from "../application/dto";
import { LessonOutlineEditor } from "./LessonOutlineEditor";
import { LessonOutlineSummary } from "./LessonOutlineSummary";

function plan(): LessonPlanResponse {
  const beat = {
    title: "Interpret the situation",
    purpose: "Connect context and interpretation",
    teachingNotes: "Explain the context before comparing interpretations.",
    concepts: ["Context"],
    seconds: 150,
    checkQuestion: "Why do the interpretations differ?",
    expectedAnswer: "Different context",
  };
  return {
    lessonId: "lesson_test",
    objectives: ["Compare interpretations"],
    assumedKnowledge: [],
    introducedKnowledge: ["Context"],
    requiredFacts: ["Context affects interpretation"],
    equations: [],
    misconceptions: [],
    scopeBoundaries: ["One situation"],
    beats: [beat, { ...beat, checkQuestion: "", expectedAnswer: "" }],
    examples: [
      {
        problem: "Two readings of one message",
        steps: [],
        result: "Context matters",
      },
    ],
    sources: [],
    feasibilityStatus: "feasible",
  };
}

it("renders one diagnostic without empty checks on the other beats", () => {
  render(<LessonOutlineSummary plan={plan()} />);
  expect(screen.getAllByText("Check your understanding")).toHaveLength(1);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("exposes the specific scope conflict and both recommendations", () => {
  render(
    <LessonOutlineSummary
      plan={{
        ...plan(),
        feasibilityStatus: "infeasible",
        feasibilityExplanation: "The comparison needs more time.",
        recommendedVideoMinutes: 12,
        recommendedScopeAdjustment:
          "Move the second objective into another lesson.",
      }}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent(
    "The comparison needs more time.",
  );
  expect(screen.getByRole("status")).toHaveTextContent("12 video minutes");
  expect(screen.getByRole("status")).toHaveTextContent(
    "Move the second objective",
  );
});

it("saves a qualitative case and leaves the unused diagnostic fields empty", () => {
  const onSave = vi.fn();
  render(
    <LessonOutlineEditor
      plan={plan()}
      minutes={5}
      topics={["Context"]}
      pending={false}
      error={null}
      onSave={onSave}
      onCancel={() => {}}
    />,
  );
  fireEvent.submit(screen.getByRole("form", { name: "Edit lesson outline" }));
  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({
      feasibilityStatus: "feasible",
      examples: [expect.objectContaining({ steps: [] })],
      beats: [
        expect.objectContaining({
          checkQuestion: "Why do the interpretations differ?",
        }),
        expect.objectContaining({ checkQuestion: "", expectedAnswer: "" }),
      ],
    }),
  );
});

it("requires exact timing when editing a newly assessed feasible plan", () => {
  const initial = plan();
  const onSave = vi.fn();
  render(
    <LessonOutlineEditor
      plan={{
        ...initial,
        beats: [
          initial.beats[0],
          {
            ...initial.beats[1],
            seconds: 151,
          },
        ],
      }}
      minutes={5}
      topics={["Context"]}
      pending={false}
      error={null}
      onSave={onSave}
      onCancel={() => {}}
    />,
  );
  fireEvent.submit(screen.getByRole("form", { name: "Edit lesson outline" }));
  expect(screen.getByRole("alert")).toHaveTextContent("exactly 300 seconds");
  expect(onSave).not.toHaveBeenCalled();
});

it("preserves infeasibility when saving an outline with estimates beyond the video limit", () => {
  const initial = plan();
  const onSave = vi.fn();
  render(
    <LessonOutlineEditor
      plan={{
        ...initial,
        beats: initial.beats.map((beat) => ({ ...beat, seconds: 360 })),
        feasibilityStatus: "infeasible",
        feasibilityExplanation: "The comparison needs more time.",
        recommendedVideoMinutes: 12,
      }}
      minutes={5}
      topics={["Context"]}
      pending={false}
      error={null}
      onSave={onSave}
      onCancel={() => {}}
    />,
  );
  fireEvent.submit(screen.getByRole("form", { name: "Edit lesson outline" }));
  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({
      feasibilityStatus: "infeasible",
      recommendedVideoMinutes: 12,
    }),
  );
});

it("rejects an infeasible outline without a duration even when it suggests a scope adjustment", () => {
  const initial = plan();
  const onSave = vi.fn();
  render(
    <LessonOutlineEditor
      plan={{
        ...initial,
        beats: initial.beats.map((beat) => ({ ...beat, seconds: 360 })),
        feasibilityStatus: "infeasible",
        feasibilityExplanation: "The comparison needs more time.",
        recommendedVideoMinutes: null,
        recommendedScopeAdjustment:
          "Move the second objective into another lesson.",
      }}
      minutes={5}
      topics={["Context"]}
      pending={false}
      error={null}
      onSave={onSave}
      onCancel={() => {}}
    />,
  );
  fireEvent.submit(screen.getByRole("form", { name: "Edit lesson outline" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "needs a duration recommendation",
  );
  expect(onSave).not.toHaveBeenCalled();
});

it.each([
  [181, 4],
  [361, 7],
])(
  "updates the duration recommendation after editing the total to %s seconds",
  (seconds, recommended) => {
    const initial = plan();
    const onSave = vi.fn();
    render(
      <LessonOutlineEditor
        plan={{
          ...initial,
          feasibilityStatus: "infeasible",
          feasibilityExplanation: "The required comparisons need more time.",
          recommendedVideoMinutes: 5,
        }}
        minutes={3}
        topics={["Context"]}
        pending={false}
        error={null}
        onSave={onSave}
        onCancel={() => {}}
      />,
    );
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Beat 1: Seconds" }),
      {
        target: { value: String(seconds - 150) },
      },
    );
    fireEvent.submit(screen.getByRole("form", { name: "Edit lesson outline" }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        feasibilityStatus: "infeasible",
        recommendedVideoMinutes: recommended,
      }),
    );
  },
);
