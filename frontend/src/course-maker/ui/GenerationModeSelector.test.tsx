import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryGenerationPreferences } from "../testing/generation-preferences";
import { GenerationModeSelector } from "./GenerationModeSelector";
import { useGenerationMode } from "./generation-mode";

function Picker({
  scope = "new-course",
  parent,
  disabled = false,
  preferences,
}: {
  scope?: string;
  parent?: string;
  disabled?: boolean;
  preferences?: MemoryGenerationPreferences;
}) {
  const [value, onChange] = useGenerationMode(
    scope,
    parent,
    undefined,
    preferences,
  );
  return (
    <GenerationModeSelector
      value={value}
      onChange={onChange}
      disabled={disabled}
    />
  );
}

describe("Generation mode", () => {
  it("defaults to Balanced, explains the tradeoff, and supports keyboard selection", async () => {
    render(<Picker />);
    const balanced = screen.getByRole("radio", {
      name: "Balanced",
    });
    expect(balanced).toBeChecked();
    balanced.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Pro" })).toBeChecked();
    expect(screen.getByText(/takes longer and costs more/)).toBeVisible();
  });
  it("inherits a course mode, saves a lesson override, and restores it after remount", async () => {
    const preferences = new MemoryGenerationPreferences();
    preferences.save("course:one", "pro");
    const first = render(
      <Picker
        scope="course-lesson:one:first"
        parent="course:one"
        preferences={preferences}
      />,
    );
    expect(screen.getByRole("radio", { name: "Pro" })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: "Fast" }));
    first.unmount();
    const second = render(
      <Picker
        scope="course-lesson:one:first"
        parent="course:one"
        preferences={preferences}
      />,
    );
    expect(screen.getByRole("radio", { name: "Fast" })).toBeChecked();
    second.unmount();
    render(
      <Picker
        scope="course-lesson:one:second"
        parent="course:one"
        preferences={preferences}
      />,
    );
    expect(screen.getByRole("radio", { name: "Pro" })).toBeChecked();
  });
  it("prevents changes while generating", async () => {
    render(<Picker disabled />);
    for (const radio of screen.getAllByRole("radio"))
      expect(radio).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: "Fast" }));
    expect(screen.getByRole("radio", { name: "Balanced" })).toBeChecked();
  });
});
