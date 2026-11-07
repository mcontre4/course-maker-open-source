import { test, expect } from "@playwright/test";

const owner = "user_00000000-0000-0000-0000-000000000001";

// The right answers are B, A, C. Learners are never told this up front.
const questions = [
  ["What does a variable do?", ["Always adds", "Names a value"], 1],
  ["What does a string hold?", ["Text", "Nothing"], 0],
  ["Which keyword defines a function?", ["let", "if", "def"], 2],
].map(([prompt, options, correctIndex], index) => ({
  id: `question_${index + 1}`,
  kind: "multiple_choice",
  prompt,
  options,
  correctIndex,
  explanation: `Because ${String(prompt).toLowerCase()}`,
}));

test("a learner sees what they got right and wrong, and a perfect score gets confetti", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  const discovery = await (
    await request.get("/api/v1/published/discovery")
  ).json();
  const lesson = discovery.lessons.find(
    (item: { title: string }) => item.title === "Newest public lesson",
  );
  const saved = await request.put(`/api/v1/lessons/${lesson.id}/quiz`, {
    headers: { "x-test-owner": owner },
    data: { questions },
  });
  expect(saved.ok()).toBeTruthy();

  await page.goto(`/watch/lessons/${lesson.id}`);
  await page
    .getByRole("navigation", { name: "Parts of this lesson" })
    .getByRole("button", { name: /Check your understanding/ })
    .click();
  const quiz = page.getByRole("region", { name: "Check your understanding" });
  const submit = quiz.getByRole("button", { name: "Submit answers" });
  await expect(submit).toBeDisabled();
  await expect(quiz).toContainText("3 questions left to answer");

  // First try: one right, two wrong.
  await quiz.getByRole("radio", { name: "Names a value" }).check();
  await quiz.getByRole("radio", { name: "Nothing" }).check();
  await quiz.getByRole("radio", { name: "if" }).check();
  await expect(quiz).toContainText("All answered");
  await submit.click();

  const summary = quiz.getByRole("status");
  await expect(summary).toContainText("You scored 1 of 3.");
  await expect(summary).toContainText("Not there yet");
  await expect(summary).toBeFocused();
  await expect(
    summary.getByRole("button", { name: "Question 1: correct" }),
  ).toBeVisible();
  await expect(
    summary.getByRole("button", { name: "Question 2: not quite" }),
  ).toBeVisible();
  await expect(
    summary.getByRole("button", { name: "Question 3: not quite" }),
  ).toBeVisible();
  const cards = quiz.locator("fieldset.learner-question");
  await expect(cards.nth(0)).toHaveAttribute("data-result", "correct");
  await expect(cards.nth(1)).toHaveAttribute("data-result", "wrong");
  await expect(cards.nth(2)).toHaveAttribute("data-result", "wrong");
  await expect(cards.nth(0)).toContainText("Correct");
  await expect(cards.nth(1)).toContainText("Not quite");
  await expect(cards.nth(1)).toContainText("Your answer");
  await expect(cards.nth(1)).toContainText("Because what does a string hold?");
  await expect(page.getByTestId("confetti")).toHaveCount(0);

  // The pills jump to their question.
  await summary.getByRole("button", { name: "Question 3: not quite" }).click();
  await expect(cards.nth(2)).toBeFocused();

  // Second try: everything right.
  await summary.getByRole("button", { name: "Try again" }).click();
  await expect(submit).toBeDisabled();
  await expect(
    quiz.getByRole("radio", { name: "Names a value" }),
  ).not.toBeChecked();
  await quiz.getByRole("radio", { name: "Names a value" }).check();
  await quiz.getByRole("radio", { name: "Text" }).check();
  await quiz.getByRole("radio", { name: "def" }).check();
  await submit.click();

  await expect(quiz.getByRole("status")).toContainText("Perfect score!");
  await expect(quiz.getByRole("status")).toContainText("You scored 3 of 3.");
  await expect(cards.nth(0)).toHaveAttribute("data-result", "correct");
  await expect(cards.nth(1)).toHaveAttribute("data-result", "correct");
  await expect(cards.nth(2)).toHaveAttribute("data-result", "correct");
  const confetti = page.getByTestId("confetti");
  await expect(confetti).toBeVisible();
  expect(await confetti.locator("i").count()).toBeGreaterThan(50);
  // Paper is falling, and it never blocks clicks.
  await expect(confetti).toHaveCSS("pointer-events", "none");
  await expect
    .poll(() =>
      confetti
        .locator("i")
        .first()
        .evaluate((node) => node.getBoundingClientRect().top),
    )
    .toBeGreaterThan(0);
  // It tidies itself away.
  await expect(confetti).toHaveCount(0, { timeout: 8000 });
  await expect(quiz).toContainText("Best score: 100%");
  expect(errors).toEqual([]);
});

test("visitors who prefer reduced motion get no confetti", async ({
  browser,
  request,
}) => {
  const discovery = await (
    await request.get("/api/v1/published/discovery")
  ).json();
  const lesson = discovery.lessons.find(
    (item: { title: string }) => item.title === "Newest public lesson",
  );
  await request.put(`/api/v1/lessons/${lesson.id}/quiz`, {
    headers: { "x-test-owner": owner },
    data: { questions },
  });
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto(`/watch/lessons/${lesson.id}`);
  await page
    .getByRole("navigation", { name: "Parts of this lesson" })
    .getByRole("button", { name: /Check your understanding/ })
    .click();
  const quiz = page.getByRole("region", { name: "Check your understanding" });
  await quiz.getByRole("radio", { name: "Names a value" }).check();
  await quiz.getByRole("radio", { name: "Text" }).check();
  await quiz.getByRole("radio", { name: "def" }).check();
  await quiz.getByRole("button", { name: "Submit answers" }).click();
  await expect(quiz.getByRole("status")).toContainText("Perfect score!");
  await expect(page.getByTestId("confetti")).toBeHidden();
  await context.close();
});
