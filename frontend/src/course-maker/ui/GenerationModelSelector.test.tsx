import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { BrowserModelPreferences } from "../adapters/persistence/browser-model-preferences";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import { GenerationModelSelector } from "./GenerationModelSelector";

it("shares the override across selectors and can return to automatic", async () => {
  const storage = { getItem: () => null, setItem: () => {} };
  const preferences = new BrowserModelPreferences(storage);
  const application = {
    ...createCourseApplication(storage, { next: () => "course_test" }),
    modelPreferences: preferences,
  };
  render(
    <ApplicationContext.Provider value={application}>
      <GenerationModelSelector mode="balanced" disabled={false} />
      <GenerationModelSelector mode="pro" disabled={true} />
    </ApplicationContext.Provider>,
  );
  const [active, disabled] = screen.getAllByRole("combobox", {
    name: "Generation model",
  });
  const user = userEvent.setup();
  await user.selectOptions(active, "anthropic/claude-opus-5.5:fast");
  expect(preferences.get()).toBe("anthropic/claude-opus-5.5:fast");
  expect(disabled).toHaveValue("anthropic/claude-opus-5.5:fast");
  expect(disabled).toBeDisabled();
  expect(
    screen.queryByRole("option", { name: /Sonnet.*Fast/ }),
  ).not.toBeInTheDocument();
  await user.selectOptions(active, "");
  expect(preferences.get()).toBe("");
  expect(disabled).toHaveValue("");
});
