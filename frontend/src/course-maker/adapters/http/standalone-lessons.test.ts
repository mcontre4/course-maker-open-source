import { expect, it } from "vitest";
import { HttpStandaloneLessons } from "./standalone-lessons";

const content = {
  id: "lesson_1",
  title: "Bonds",
  image: "",
  topics: ["Bonds"],
  minutes: 3,
  video_url: null,
  quiz: [],
  storyboard: null,
  alignment: null,
  animation: null,
  plan: {
    lesson_id: "lesson_1",
    objectives: ["Understand bonds"],
    assumed_knowledge: [],
    introduced_knowledge: ["Bonds"],
    required_facts: ["Atoms share electrons"],
    equations: [],
    misconceptions: [],
    scope_boundaries: ["Introductory"],
    beats: [
      {
        title: "Atoms",
        purpose: "Explain",
        teaching_notes: "Notes",
        concepts: ["Bonds"],
        seconds: 240,
        check_question: "",
        expected_answer: "",
      },
    ],
    examples: [{ problem: "Water", steps: ["Share"], result: "H2O" }],
    sources: [],
    feasibility_status: "infeasible",
    feasibility_explanation: "Needs more time.",
    recommended_video_minutes: 4,
    recommended_scope_adjustment: "Drop one objective.",
  },
};

it("keeps the feasibility assessment so the lesson can offer a fix", async () => {
  const backend = new HttpStandaloneLessons(async (path) =>
    Response.json(
      path.endsWith("/spend")
        ? { steps: [], total_cost_usd: 0 }
        : {
            id: "lesson_1",
            owner_id: "user_1",
            flow: "guided",
            description: "Bonds",
            revision: 1,
            approved: false,
            turns: [],
            content,
          },
    ),
  );
  const { content: lesson } = await backend.get("lesson_1");
  expect(lesson.plan).toMatchObject({
    feasibilityStatus: "infeasible",
    feasibilityExplanation: "Needs more time.",
    recommendedVideoMinutes: 4,
    recommendedScopeAdjustment: "Drop one objective.",
  });
});
