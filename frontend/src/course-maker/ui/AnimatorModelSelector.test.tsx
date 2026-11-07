import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import type { AnimatorModelChoice } from "../application/animator-model";
import type { GenerationMode } from "../application/generation-mode";
import { AnimatorModelSelector } from "./AnimatorModelSelector";

function Picker({
  mode,
  disabled = false,
}: {
  mode: GenerationMode;
  disabled?: boolean;
}) {
  const [value, onChange] = useState<AnimatorModelChoice>("");
  return (
    <AnimatorModelSelector
      value={value}
      onChange={onChange}
      mode={mode}
      disabled={disabled}
    />
  );
}

it("follows the mode automatically and keeps an explicit selection until cleared", async () => {
  const view = render(<Picker mode="fast" />);
  const select = screen.getByRole("combobox", { name: "Animator model" });
  expect(select).toHaveValue("");
  expect(
    screen.getByRole("option", { name: /Automatic — Claude Sonnet 5.5/ }),
  ).toBeVisible();
  expect(
    screen.getByText(/Claude Sonnet 5.5: \$2 input \/ \$10 output/),
  ).toBeVisible();
  view.rerender(<Picker mode="pro" />);
  expect(
    screen.getByRole("option", { name: /Automatic — Claude Opus 5.5/ }),
  ).toBeVisible();
  await userEvent.selectOptions(select, "anthropic/claude-opus-5.5");
  expect(
    screen.getByText(/Claude Opus 5.5: \$4 input \/ \$20 output/),
  ).toBeVisible();
  view.rerender(<Picker mode="balanced" />);
  expect(select).toHaveValue("anthropic/claude-opus-5.5");
  await userEvent.selectOptions(select, "");
  expect(
    screen.getByRole("option", { name: /Automatic — Claude Opus 5.5/ }),
  ).toBeVisible();
  expect(
    screen.getByText(/Claude Opus 5.5: \$4 input \/ \$20 output/),
  ).toBeVisible();
});

it("locks model changes during generation and offers all ten supported choices", () => {
  render(<Picker mode="balanced" disabled />);
  expect(
    screen.getByRole("combobox", { name: "Animator model" }),
  ).toBeDisabled();
  expect(screen.getAllByRole("option")).toHaveLength(11);
  expect(screen.getByText(/Applies to animation and AI review/)).toBeVisible();
});

it.each([
  ["openai/gpt-6-luna:fast", "GPT-6 Luna Fast: $0.2 input / $1 output"],
  ["openai/gpt-6.1-terra:fast", "GPT-6.1 Terra Fast: $2 input / $10 output"],
  ["openai/gpt-6.1-sol:fast", "GPT-6.1 Sol Fast: $4 input / $20 output"],
])("selects %s and displays its Fast pricing", async (model, price) => {
  render(<Picker mode="balanced" />);
  const select = screen.getByRole("combobox", { name: "Animator model" });
  await userEvent.selectOptions(select, model);
  expect(select).toHaveValue(model);
  expect(screen.getByText(price, { exact: false })).toBeVisible();
});

it("explains the higher rate for Haiku prompts over 100K tokens", async () => {
  render(<Picker mode="balanced" />);
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Animator model" }),
    "anthropic/claude-haiku-5.5",
  );
  expect(
    screen.getByText(/Claude Haiku 5.5: \$0.1 input \/ \$0.5 output/),
  ).toBeVisible();
  expect(
    screen.getByText(
      /For prompts over 100K tokens: \$0.50 input \/ \$2.50 output/,
    ),
  ).toBeVisible();
});
