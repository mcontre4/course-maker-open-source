import { test, expect } from "@playwright/test";

test("creates a lesson, reviews and edits narration, plays video, and safely replaces it", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/lessons/new");
  await expect(page.getByLabel("Who is this for?")).toBeVisible();
  await page.getByLabel("Lesson title", { exact: true }).fill("Rain pipeline");
  await page
    .getByLabel("What would you like to learn?", { exact: true })
    .fill("Explain how rain forms for beginners.");
  await page.getByLabel("Who is this for?", { exact: true }).fill("Beginners");
  await page.getByRole("radio", { name: /^Flat-Vector Science/ }).check();
  await page.getByRole("button", { name: "1 min", exact: true }).click();
  await page.getByText("Guided", { exact: true }).click();
  await page.getByRole("button", { name: "Build my lesson outline →" }).click();
  await expect(
    page.getByRole("heading", { name: "Review your lesson outline" }),
  ).toBeVisible();
  const id = new URL(page.url()).pathname.split("/").at(-1)!;
  const guide = page.getByLabel("Message your lesson guide", { exact: true });
  await guide.fill("An unsent thought");
  await expect(
    page.getByRole("button", { name: "Script", exact: true }),
  ).toBeDisabled();
  await expect(guide).toBeEnabled();
  await guide.fill("");
  await page.getByRole("button", { name: "Edit outline", exact: true }).click();
  await page
    .getByLabel("Beat 1: Title", { exact: true })
    .fill("Follow one drop of water");
  await page.getByRole("button", { name: "Save outline", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Follow one drop of water" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Review script first", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Script & narration" }),
  ).toBeVisible();
  const beforeScript = await (
    await request.get(`/api/v1/lessons/${id}`)
  ).json();
  expect(beforeScript.content.alignment).toBeNull();
  expect(beforeScript.content.animation).toBeNull();
  await page.getByRole("button", { name: "Edit script", exact: true }).click();
  const narration = page.getByLabel("Narration for scene 1", { exact: true });
  const original = await narration.inputValue();
  await narration.fill("Think about a drop of rain. " + original);
  await page.getByRole("button", { name: "Save script", exact: true }).click();
  await expect(narration).toHaveCount(0);
  await page
    .getByRole("button", { name: "Create video →", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
  const video = page.getByLabel("Rain pipeline video", { exact: true });
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(2);
  await video.evaluate((v: HTMLVideoElement) => v.play());
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
    .toBeGreaterThan(0);
  await video.evaluate((v: HTMLVideoElement) => v.pause());
  const oldUrl = await video.getAttribute("src");
  expect(await video.evaluate((v: HTMLVideoElement) => v.error)).toBeNull();
  await page.screenshot({
    path: "test-results/lesson-workflow-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "View script", exact: true }).click();
  await page.getByRole("button", { name: "Edit script", exact: true }).click();
  await narration.fill("Keep this unsaved review. " + original);
  await page.goBack();
  await expect(narration).toHaveValue("Keep this unsaved review. " + original);
  await page
    .getByRole("button", { name: "Cancel script edits", exact: true })
    .click();
  await page.getByRole("button", { name: "Edit video", exact: true }).click();
  await page.getByRole("button", { name: "Script", exact: true }).click();
  await page.getByRole("button", { name: "Edit script", exact: true }).click();
  await narration.fill("Now follow this example. " + original);
  await page.getByRole("button", { name: "Save script", exact: true }).click();
  await expect(
    page.getByText("Editing a new draft.", { exact: true }),
  ).toBeVisible();
  await expect(video).toHaveAttribute("src", oldUrl!);
  const draft = await (await request.get(`/api/v1/lessons/${id}`)).json();
  expect(draft.playbackContent.animation.outputHash).toBe(
    new URL(oldUrl!, page.url()).searchParams.get("v"),
  );
  expect(draft.content.animation).toBeNull();
  await page
    .getByRole("button", { name: "Watch current video", exact: true })
    .click();
  await expect(video).toHaveAttribute("src", oldUrl!);
  await page
    .getByRole("button", { name: "Continue editing", exact: true })
    .click();
  await page.getByRole("button", { name: "Script", exact: true }).click();
  await expect(
    page.getByText("Now follow this example. " + original, { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate updated video →", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
  await expect(video).not.toHaveAttribute("src", oldUrl!);
  expect(
    (await request.get(oldUrl!, { headers: { Range: "bytes=0-31" } })).status(),
  ).toBe(206);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Edit video", exact: true }).click();
  await page.getByRole("button", { name: "Script", exact: true }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/lesson-workflow-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("resumes a failed generation from persisted script and narration after reload", async ({
  page,
}) => {
  await page.goto("/lessons/new");
  await page.getByLabel("Lesson title", { exact: true }).fill("Retry once");
  await page
    .getByLabel("What would you like to learn?", { exact: true })
    .fill("Explain a simple idea.");
  await page.getByRole("radio", { name: /^Flat-Vector Science/ }).check();
  await page.getByRole("button", { name: "1 min", exact: true }).click();
  await page.getByText("Guided", { exact: true }).click();
  await page.getByRole("button", { name: "Build my lesson outline →" }).click();
  await expect(
    page.getByRole("heading", { name: "Review your lesson outline" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create video →", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("interrupted");
  await expect(page.getByLabel("Video generation progress")).toContainText(
    "Saved",
  );
  await page.reload();
  await expect(
    page.getByRole("button", {
      name: "Continue video generation →",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByLabel("Video generation progress")).toContainText(
    "Narration",
  );
  await page
    .getByRole("button", { name: "Continue video generation →", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
});

test("saves voice and visual preferences and guides the user through an outline rebuild", async ({
  page,
  request,
}) => {
  await page.goto("/lessons/new");
  await page
    .getByLabel("Lesson title", { exact: true })
    .fill("Voice and visuals");
  await page
    .getByLabel("What would you like to learn?", { exact: true })
    .fill("Explain the water cycle.");
  await page.getByRole("radio", { name: /^Flat-Vector Science/ }).check();
  await page.getByRole("button", { name: "1 min", exact: true }).click();
  await page.getByText("Guided", { exact: true }).click();
  await page.getByRole("button", { name: "Build my lesson outline →" }).click();
  await page
    .getByRole("button", { name: "Create video →", exact: true })
    .click();
  await page.getByRole("button", { name: "Edit video", exact: true }).click();
  const id = new URL(page.url()).pathname.split("/").at(-1)!;
  const video = page.getByLabel("Voice and visuals video", { exact: true });
  const oldUrl = await video.getAttribute("src");
  await page.getByRole("button", { name: "Voice", exact: true }).click();
  await page.getByLabel("Pacing", { exact: true }).selectOption("Relaxed");
  await page.getByRole("button", { name: "Save voice", exact: true }).click();
  await expect(
    page.getByText("Editing a new draft.", { exact: true }),
  ).toBeVisible();
  await expect(video).toHaveAttribute("src", oldUrl!);
  await page
    .getByRole("button", { name: "Review outline →", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Generate lesson outline →", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review your lesson outline" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Visuals", exact: true }).click();
  await page
    .getByLabel("Visual instructions", { exact: true })
    .fill("Simple labeled diagrams with gentle movement.");
  await page.getByRole("button", { name: "Save visuals", exact: true }).click();
  await expect(
    page.getByText(/Saved\. Generate an updated video/),
  ).toBeVisible();
  const lesson = await (await request.get(`/api/v1/lessons/${id}`)).json();
  expect(lesson.content.style.request).toBe(
    "Simple labeled diagrams with gentle movement.",
  );
  expect(lesson.content.style.requestedPacing).toBe("Relaxed");
  expect(lesson.playbackContent.animation.outputHash).toBe(
    new URL(oldUrl!, page.url()).searchParams.get("v"),
  );
  await page.reload();
  await page.getByRole("button", { name: "Visuals", exact: true }).click();
  await expect(
    page.getByLabel("Visual instructions", { exact: true }),
  ).toHaveValue("Simple labeled diagrams with gentle movement.");
});
