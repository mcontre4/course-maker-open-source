import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentMessages, AgentThread } from "./AgentThread";

const renderAnswer = (assistant: string) =>
  render(
    <AgentThread
      turns={[{ id: "one", user: "Help me learn", assistant }]}
      onSend={() => {}}
    >
      <AgentMessages />
    </AgentThread>,
  );

describe("agent answers", () => {
  it("does not mistake a programming explanation for generated UI", () => {
    renderAnswer("root = 2\n\nThis variable stores the square root.");
    expect(screen.getByText("root = 2")).toBeVisible();
    expect(
      screen.getByText("This variable stores the square root."),
    ).toBeVisible();
    expect(
      screen.queryByText(/This answer could not be displayed/),
    ).not.toBeInTheDocument();
  });
  it("also renders an unfenced OpenUI reply", async () => {
    renderAnswer(
      'root = Answer("A direct answer", "Use a concrete example.", [])',
    );
    expect(
      await screen.findByRole("heading", { name: "A direct answer" }),
    ).toBeVisible();
  });
  it("renders generated OpenUI explanations, steps, comparisons and takeaways", async () => {
    renderAnswer(
      '```openui\nroot = Answer("Understanding bonds", "Atoms form more stable arrangements.", [Explanation("The idea", "Electrons determine the bond."), Steps("Try it", ["Count electrons", "Compare stability"]), Comparison("Two bonds", ["Bond", "Electrons"], [["Ionic", "Transferred"], ["Covalent", "Shared"]]), Callout("Remember", "Start with the outer shell.")])\n```',
    );
    expect(
      await screen.findByRole("heading", { name: "Understanding bonds" }),
    ).toBeVisible();
    expect(screen.getByRole("list")).toHaveTextContent("Count electrons");
    expect(screen.getByRole("table")).toHaveTextContent("CovalentShared");
    expect(screen.getByText("Start with the outer shell.")).toBeVisible();
    expect(screen.queryByText(/root = Answer/)).not.toBeInTheDocument();
  });

  it("keeps Markdown history readable with headings, lists and code", () => {
    renderAnswer(
      "### A small example\n\nUse **two** steps:\n\n1. Read `x`\n2. Compare it\n\n```python\nx = 2\n```",
    );
    expect(
      screen.getByRole("heading", { name: "A small example" }),
    ).toBeVisible();
    expect(screen.getByRole("list")).toBeVisible();
    expect(screen.getByText("two").tagName).toBe("STRONG");
    expect(screen.getByText("x = 2")).toBeVisible();
  });

  it.each([
    'root = Unknown("Oops")',
    "root = Answer(null)",
    'root = Answer("Incomplete", "',
    'root = Answer("Missing", "Reference", [missing])',
  ])("contains invalid generated answers: %s", async (source) => {
    renderAnswer("```openui\n" + source + "\n```");
    expect(
      await screen.findByText(/This answer could not be displayed/),
    ).toBeVisible();
    expect(screen.getByText("Help me learn")).toBeVisible();
  });

  it("treats generated strings and user messages as text", async () => {
    const { container } = renderAnswer(
      '```openui\nroot = Answer("Safety", "<script>alert(1)</script>", [Explanation("Example", "<img src=x onerror=alert(1)>")])\n```',
    );
    expect(container.querySelector("script, img")).toBeNull();
    expect(await screen.findByText("<script>alert(1)</script>")).toBeVisible();
  });
});
