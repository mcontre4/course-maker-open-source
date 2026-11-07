import { test, expect } from "@playwright/test";

test("infers missing details and regenerates every stage with fake providers", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/lessons/new");
  await page
    .getByLabel("Lesson title", { exact: true })
    .fill("Rain regeneration");
  await page.getByRole("radio", { name: /^Flat-Vector Science/ }).check();
  await page.getByText("Guided", { exact: true }).click();
  await page.getByRole("button", { name: "1 min", exact: true }).click();
  await page.getByRole("button", { name: "Build my lesson outline →" }).click();
  await expect(
    page.getByRole("heading", { name: "Review your lesson outline" }),
  ).toBeVisible();
  const id = new URL(page.url()).pathname.split("/").at(-1)!;
  const read = async () => (await request.get(`/api/v1/lessons/${id}`)).json();
  expect((await read()).description).toBe("Rain regeneration");
  await page
    .getByRole("button", { name: "Review script first", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Regenerate script", exact: true }),
  ).toBeEnabled();
  const scriptResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/lessons/${id}/script/generate`) &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Regenerate script", exact: true })
    .click();
  expect((await scriptResponse).status()).toBe(200);
  expect((await read()).content.alignment).toBeNull();
  const videoResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/lessons/${id}/video`) &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Create video →", exact: true })
    .click();
  expect((await videoResponse).status()).toBe(200);
  for (const [restart, option] of [
    ["animation", "Animation only"],
    ["speech", "From the narration"],
    ["script", "From the script"],
    ["outline", "Everything"],
  ]) {
    await page.getByRole("button", { name: "Edit video", exact: true }).click();
    const before = await read();
    await page.locator("details.quality-settings > summary").click();
    await page
      .getByRole("group", { name: "Quality & speed", exact: true })
      .getByText("Pro", { exact: true })
      .click();
    const response = page.waitForResponse(
      (r) =>
        r
          .url()
          .endsWith(
            `/lessons/${id}/${restart === "outline" ? "automatic" : "video"}`,
          ) && r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Regenerate video", exact: true })
      .click();
    await page.getByRole("button", { name: option, exact: true }).click();
    const result = await response;
    expect(result.status()).toBe(200);
    expect(result.request().postDataJSON().generationMode).toBe("pro");
    if (restart !== "outline")
      expect(result.request().postDataJSON().regenerateFrom).toBe(restart);
    const saved = await read();
    expect(saved.revision).toBeGreaterThan(before.revision);
    expect(saved.content.animation).not.toBeNull();
    if (restart === "animation") {
      expect(saved.content.storyboard).toEqual(before.content.storyboard);
      expect(saved.content.alignment).toEqual(before.content.alignment);
    }
    if (restart === "speech")
      expect(saved.content.storyboard).toEqual(before.content.storyboard);
    await expect(
      page.getByRole("button", { name: "Edit video", exact: true }),
    ).toBeVisible();
  }
  expect(errors).toEqual([]);
});
