import { test, expect } from "@playwright/test";

test("advanced narration settings are collapsed, previewable and persist with a lesson draft", async ({
  page,
}, testInfo) => {
  await page.route("**/api/v1/voices", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "american",
            name: "American teacher",
            description: "Warm educational narrator",
            labels: ["accent: American"],
            previewUrl: "https://example.com/sample.mp3",
          },
          {
            id: "british",
            name: "British teacher",
            description: "Measured narrator",
            labels: ["accent: British"],
            previewUrl: null,
          },
        ],
      },
    }),
  );
  await page.goto("/lessons/new");
  const quality = page.getByRole("group", { name: "Quality & speed" });
  for (const name of ["Fast", "Balanced", "Pro"]) {
    await expect(quality.getByRole("radio", { name })).toBeVisible();
  }
  await expect(quality.getByLabel("Generation model")).not.toBeVisible();
  await quality.getByRole("radio", { name: "Pro" }).check();
  await expect(page.getByLabel("Tone", { exact: true })).not.toBeVisible();
  await page.getByText("Voice & delivery preferences", { exact: true }).click();
  await page.getByRole("radio", { name: /^Flat-Vector Science/ }).check();
  await expect(page.getByLabel("Accent", { exact: true })).toHaveValue(
    "American",
  );
  await expect(page.getByLabel("Narrator voice").locator("option")).toHaveCount(
    2,
  );
  await page.getByLabel("Narrator voice").selectOption("american");
  await expect(page.getByLabel("Preview American teacher")).toHaveAttribute(
    "src",
    "https://example.com/sample.mp3",
  );
  await page.getByLabel("Tone", { exact: true }).selectOption("custom");
  await page
    .getByLabel("Custom tone", { exact: true })
    .fill("Calm and reassuring");
  await page.getByLabel("Pacing", { exact: true }).selectOption("Relaxed");
  await page.getByLabel("Who is this for?").fill("Beginners");
  await page.getByLabel("Lesson title").fill("Rainbows");
  await page
    .getByLabel("What would you like to learn?")
    .fill("Explain why rainbows appear");
  await page.screenshot({
    path: testInfo.outputPath("advanced-settings.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Save as draft" }).click();
  await expect(
    page.getByRole("button", { name: "Save as draft" }),
  ).toBeDisabled();
  await expect(page).toHaveURL(/\/lessons\/lesson_[^/]+\/edit$/);
  await page.reload();
  await expect(quality.getByRole("radio", { name: "Pro" })).toBeChecked();
  await expect(quality.getByLabel("Generation model")).not.toBeVisible();
  await expect(page.getByLabel("Tone", { exact: true })).not.toBeVisible();
  await page.getByText("Voice & delivery preferences", { exact: true }).click();
  await expect(page.getByLabel("Custom tone", { exact: true })).toHaveValue(
    "Calm and reassuring",
  );
  await expect(page.getByLabel("Pacing", { exact: true })).toHaveValue(
    "Relaxed",
  );
  await expect(page.getByLabel("Narrator voice")).toHaveValue("american");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const name of ["Fast", "Balanced", "Pro"]) {
    await expect(quality.getByRole("radio", { name })).toBeVisible();
  }
  await page.screenshot({
    path: testInfo.outputPath("advanced-settings-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("course creation exposes quality and speed while keeping technical settings secondary", async ({
  page,
}, testInfo) => {
  await page.goto("/courses/new");
  const quality = page.getByRole("group", { name: "Quality & speed" });
  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    for (const name of ["Fast", "Balanced", "Pro"]) {
      await expect(quality.getByRole("radio", { name })).toBeVisible();
    }
    await expect(quality.getByLabel("Generation model")).not.toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: testInfo.outputPath(`course-quality-${viewport.width}.png`),
      fullPage: true,
    });
  }
  await quality.getByRole("radio", { name: "Fast" }).check();
  await expect(quality.getByRole("radio", { name: "Fast" })).toBeChecked();
  await quality.getByText("Technical settings", { exact: true }).click();
  await expect(quality.getByLabel("Generation model")).toBeVisible();
});
