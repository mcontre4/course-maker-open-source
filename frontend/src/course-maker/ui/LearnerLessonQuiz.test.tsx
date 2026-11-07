import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { createApiCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import { LearnerLessonQuiz } from "./LearnerLessonQuiz";

class QuizHttp {
  attempts: unknown[] = [];
  submissions: unknown[] = [];
  transport = async (url: string, init?: RequestInit) => {
    if (url.endsWith("/submit")) {
      const body = JSON.parse(String(init?.body));
      this.submissions.push(body);
      const key = [1, 0];
      const marks = key.map((right, i) => body.answers[i] === right);
      const result = {
        id: "attempt_1",
        quizRevision: 2,
        answers: body.answers,
        score: marks.filter(Boolean).length,
        total: key.length,
        passed: marks.filter(Boolean).length >= 1,
        submittedAt: "2026-11-01T12:00:00Z",
        feedback: [
          {
            questionId: "q1",
            correct: marks[0],
            explanation: "A name refers to a value.",
          },
          {
            questionId: "q2",
            correct: marks[1],
            explanation: "Strings hold text.",
          },
        ],
      };
      this.attempts.unshift(result);
      return Response.json(result, { status: 201 });
    }
    if (url.endsWith("/attempts"))
      return Response.json({ items: this.attempts });
    return Response.json({
      lessonId: "lesson_1",
      revision: 2,
      questions: [
        {
          id: "q1",
          kind: "multiple_choice",
          prompt: "What does a variable do?",
          options: ["Always adds", "Names a value"],
        },
        {
          id: "q2",
          kind: "multiple_choice",
          prompt: "What does a string hold?",
          options: ["Text", "Nothing"],
        },
      ],
    });
  };
}

function show(server: QuizHttp) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <ApplicationContext.Provider
        value={createApiCourseApplication(server.transport)}
      >
        <LearnerLessonQuiz lessonId="lesson_1" />
      </ApplicationContext.Provider>
    </QueryClientProvider>,
  );
}

describe("public lesson quiz", () => {
  it("shows which answers were right and wrong, without confetti", async () => {
    const server = new QuizHttp();
    const view = show(server);
    const submit = await screen.findByRole("button", {
      name: "Submit answers",
    });
    expect(submit).toBeDisabled();
    expect(screen.getByText("2 questions left to answer")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Names a value" }));
    expect(screen.getByText("1 question left to answer")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Nothing" }));
    await userEvent.click(submit);
    expect(await screen.findByText("You scored 1 of 2.")).toBeInTheDocument();
    expect(server.submissions).toEqual([{ quizRevision: 2, answers: [1, 1] }]);
    expect(screen.getByText("Nice work, you passed")).toBeInTheDocument();
    expect(screen.getByText("Correct")).toBeInTheDocument();
    expect(screen.getByText("Not quite")).toBeInTheDocument();
    expect(screen.getByText("A name refers to a value.")).toBeInTheDocument();
    expect(screen.getByText("Strings hold text.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Question 1: correct" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Question 2: not quite" }),
    ).toBeInTheDocument();
    expect(
      view.container.querySelector("fieldset[data-result='correct']"),
    ).not.toBeNull();
    expect(
      view.container.querySelector("fieldset[data-result='wrong']"),
    ).not.toBeNull();
    expect(screen.queryByTestId("confetti")).toBeNull();
    await waitFor(() =>
      expect(screen.getByText(/Best score: 50%/)).toBeInTheDocument(),
    );
    view.unmount();
    show(server);
    expect(await screen.findByText(/Best score: 50%/)).toBeInTheDocument();
  });

  it("celebrates a perfect score and lets the learner start over", async () => {
    const server = new QuizHttp();
    show(server);
    await userEvent.click(
      await screen.findByRole("radio", { name: "Names a value" }),
    );
    await userEvent.click(screen.getByRole("radio", { name: "Text" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Submit answers" }),
    );
    expect(await screen.findByText("Perfect score!")).toBeInTheDocument();
    expect(screen.getByText("You scored 2 of 2.")).toBeInTheDocument();
    expect(screen.getByTestId("confetti")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.queryByTestId("confetti")).toBeNull();
    expect(screen.queryByText("Perfect score!")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Submit answers" }),
    ).toBeDisabled();
  });
});
