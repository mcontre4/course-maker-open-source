import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it } from "vitest";
import { createApiCourseApplication } from "../../composition";
import { ApplicationContext } from "../application-context";
import { LessonPlan } from "./LessonPlan";

it("renders the complete camelCase HTTP plan contract", () => {
  const plan = {
    lessonId: "lesson_test",
    objectives: ["Explain force"],
    assumedKnowledge: ["Addition"],
    introducedKnowledge: ["Net force"],
    requiredFacts: ["Force changes velocity"],
    equations: ["F=ma"],
    misconceptions: [
      "Motion needs force: correction, acceleration needs force",
    ],
    scopeBoundaries: ["Constant mass only"],
    beats: [
      {
        title: "Net force",
        purpose: "Combine forces",
        teachingNotes: "Add signed forces",
        concepts: ["Net force"],
        seconds: 300,
        checkQuestion: "What is 7N minus 3N?",
        expectedAnswer: "4N",
      },
    ],
    examples: [{ problem: "Two pushes", steps: ["7 - 3"], result: "4 N" }],
    sources: [{ title: "Physics source", url: "https://example.com/physics" }],
  };
  render(
    <ApplicationContext.Provider value={createApiCourseApplication(fetch)}>
      <QueryClientProvider client={new QueryClient()}>
        <LessonPlan
          courseId="course_test"
          lesson={{
            id: "lesson_test",
            title: "Forces",
            image: "",
            topics: ["Net force"],
            minutes: 5,
            videoUrl: null,
            quiz: [],
            plan,
          }}
        />
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  expect(
    screen.getByRole("heading", { name: "Your lesson plan" }),
  ).toBeVisible();
  expect(screen.getByText("Add signed forces")).toBeVisible();
  expect(screen.getByText("Addition")).toBeVisible();
  expect(screen.getByRole("link", { name: "Physics source" })).toHaveAttribute(
    "href",
    "https://example.com/physics",
  );
  expect(
    screen.queryByRole("button", { name: "Generate lesson plan" }),
  ).not.toBeInTheDocument();
});
