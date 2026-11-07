import { test, expect } from "@playwright/test";

const OWNER = "user_00000000-0000-0000-0000-000000000001";
const OTHER = "user_00000000-0000-0000-0000-000000000002";

for (const [flow, operation] of [
  ["guided", "plan"],
  ["guided", "script/generate"],
  ["guided", "video"],
  ["automatic", "automatic"],
] as const) {
  test(`copies a saved ${flow} draft while ${operation} is generating`, async ({
    page,
    request,
  }) => {
    const source = await (
      await request.post("/api/v1/lessons", {
        data: {
          title: "Copy during generation",
          description: "Explain rain for beginners",
          minutes: 1,
          flow,
          style: { visualStyleId: "flat-vector-science" },
        },
      })
    ).json();
    // Keep the editor in a generating state while the real copy endpoint
    // reads the saved draft, which has no outline or generated artifacts yet.
    await page.route(`**/api/v1/lessons/${source.id}`, async (route) => {
      await route.fulfill({
        json: { ...source, activeOperation: operation },
      });
    });
    await page.goto(`/lessons/${source.id}`);
    const copyButton = page.getByRole("button", {
      name: "Copy lesson",
      exact: true,
    });
    await expect(copyButton).toBeEnabled();
    await copyButton.click();
    await page
      .getByRole("dialog", { name: "Copy this lesson" })
      .getByRole("button", { name: "Create copy", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Copy during generation-copy",
        exact: true,
      }),
    ).toBeVisible();
    const copyId = new URL(page.url()).pathname.split("/").at(-1)!;
    expect(copyId).not.toBe(source.id);
    const copy = await (await request.get(`/api/v1/lessons/${copyId}`)).json();
    expect(copy.content.plan).toBeNull();
    expect(copy.activeOperation).toBeUndefined();
    expect(copy.content.minutes).toBe(source.content.minutes);
    expect(copy.content.style).toEqual(source.content.style);
    const savedSource = await (
      await request.get(`/api/v1/lessons/${source.id}`)
    ).json();
    expect(savedSource).toEqual(source);
  });
}

test("copies an owned draft from the editor and generates the copy independently", async ({
  page,
  request,
}) => {
  const source = await (
    await request.post("/api/v1/lessons", {
      data: {
        title: "Copy my draft",
        description: "Explain rain for beginners",
        minutes: 1,
        style: { visualStyleId: "flat-vector-science" },
      },
    })
  ).json();
  await page.goto(`/lessons/${source.id}`);
  await page.getByRole("button", { name: "Copy lesson", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Copy this lesson" });
  const title = sheet.getByLabel("Title", { exact: true });
  await expect(title).toHaveValue("Copy my draft-copy");
  await expect(title).toBeFocused();
  await title.fill("Rain, my way");
  await sheet.getByRole("button", { name: "Create copy", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Rain, my way", exact: true }),
  ).toBeVisible();
  await expect(sheet).toBeHidden();
  const copyId = new URL(page.url()).pathname.split("/").at(-1)!;
  expect(copyId).not.toBe(source.id);
  const copy = await (await request.get(`/api/v1/lessons/${copyId}`)).json();
  expect(copy.ownerId).toBe(OWNER);
  expect(copy.content.title).toBe("Rain, my way");
  await page
    .getByRole("button", { name: "Generate lesson outline →", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review your lesson outline" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create video →", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
  const savedSource = await (
    await request.get(`/api/v1/lessons/${source.id}`)
  ).json();
  expect(savedSource).toEqual(source);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Rain, my way", exact: true }),
  ).toBeVisible();
});

test("cancelling the copy sheet leaves the workspace untouched", async ({
  page,
  request,
}) => {
  const source = await (
    await request.post("/api/v1/lessons", {
      data: {
        title: "Keep me as is",
        description: "Explain wind",
        minutes: 1,
        style: { visualStyleId: "flat-vector-science" },
      },
    })
  ).json();
  const before = (await (await request.get("/api/v1/lessons")).json()).items
    .length;
  await page.goto(`/lessons/${source.id}`);
  await page.getByRole("button", { name: "Copy lesson", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Copy this lesson" });
  await expect(sheet).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await page.getByRole("button", { name: "Copy lesson", exact: true }).click();
  await sheet.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(sheet).toBeHidden();
  await expect(page).toHaveURL(new RegExp(`/lessons/${source.id}`));
  expect(
    (await (await request.get("/api/v1/lessons")).json()).items,
  ).toHaveLength(before);
});

test("another user copies a finished lesson, edits and regenerates it, but cannot copy drafts", async ({
  page,
  request,
}) => {
  const discovery = await (
    await request.get("/api/v1/published/discovery")
  ).json();
  const lesson = discovery.lessons.find(
    (item: { title: string }) => item.title === "Newest public lesson",
  );
  expect(lesson).toBeTruthy();
  await page.setExtraHTTPHeaders({ "X-Test-Owner": OTHER });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/watch/lessons/${lesson.id}`);
  await page.getByRole("button", { name: "Copy lesson", exact: true }).click();
  await page
    .getByRole("dialog", { name: "Copy this lesson" })
    .getByRole("button", { name: "Create copy", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Newest public lesson-copy",
      exact: true,
    }),
  ).toBeVisible();
  const copyId = new URL(page.url()).pathname.split("/").at(-1)!;
  const headers = { "X-Test-Owner": OTHER };
  const copy = await (
    await request.get(`/api/v1/lessons/${copyId}`, { headers })
  ).json();
  expect(copy.ownerId).toBe(OTHER);
  expect(copy.content.plan.lesson_id ?? copy.content.plan.lessonId).toBe(
    copyId,
  );
  expect(copy.content.animation).toBeTruthy();
  const originalHash = copy.content.animation.outputHash;
  expect((await request.get(`/api/v1/lessons/${copyId}`)).status()).toBe(404);
  await page.getByRole("button", { name: "Script", exact: true }).click();
  await page.getByRole("button", { name: "Edit script", exact: true }).click();
  const narration = page.getByLabel("Narration for scene 1", { exact: true });
  await narration.fill(
    "My own introduction. " + (await narration.inputValue()),
  );
  await page.getByRole("button", { name: "Save script", exact: true }).click();
  await page
    .getByRole("button", { name: "Generate updated video →", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
  const video = page.getByLabel("Newest public lesson-copy video", {
    exact: true,
  });
  await expect(video).not.toHaveAttribute("src", new RegExp(originalHash));
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(2);
  const source = await (
    await request.get(`/api/v1/lessons/${lesson.id}`)
  ).json();
  expect(source.ownerId).toBe(OWNER);
  expect(source.content.title).toBe("Newest public lesson");
  const denied = await request.post(
    "/api/v1/lessons/lesson_00000000-0000-0000-0000-000000000098/copy",
    { headers, data: {} },
  );
  expect(denied.status()).toBe(404);
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Newest public lesson-copy",
      exact: true,
    }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
