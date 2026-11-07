import { test, expect } from "@playwright/test";

test("automatic lesson uses one server operation, persists its flow, and plays after reload", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  const operations: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (req) => {
    if (
      req.method() === "POST" &&
      /\/lessons\/[^/]+\/(automatic|plan|video)$/.test(req.url())
    )
      operations.push(new URL(req.url()).pathname.split("/").at(-1)!);
  });
  await page.goto("/lessons/new");
  await expect(
    page.getByRole("radio", { name: "Automatic", exact: true }),
  ).toBeChecked();
  await page.getByLabel("Lesson title", { exact: true }).fill("Automatic rain");
  await page
    .getByLabel("What would you like to learn?", { exact: true })
    .fill("Explain how rain forms.");
  await page.getByRole("radio", { name: /^Flat-Vector Science/ }).check();
  await page.getByRole("button", { name: "1 min", exact: true }).click();
  await page
    .getByRole("button", { name: "Create my lesson →", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit video", exact: true }),
  ).toBeVisible();
  expect(operations).toEqual(["automatic"]);
  const id = new URL(page.url()).pathname.split("/").at(-1)!;
  const saved = await (await request.get(`/api/v1/lessons/${id}`)).json();
  expect(saved.flow).toBe("automatic");
  expect(saved.approved).toBe(true);
  expect(saved.content.plan).not.toBeNull();
  expect(saved.content.storyboard).not.toBeNull();
  expect(saved.content.alignment).not.toBeNull();
  expect(saved.content.animation).not.toBeNull();
  await page.reload();
  const video = page.getByLabel("Automatic rain video", { exact: true });
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(2);
  await video.evaluate((v: HTMLVideoElement) => v.play());
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
    .toBeGreaterThan(0);
  await video.evaluate((v: HTMLVideoElement) => v.pause());
  expect(operations).toEqual(["automatic"]);
  await page.goto(`/lessons/${id}/edit`);
  await expect(
    page.getByRole("radio", { name: "Automatic", exact: true }),
  ).toBeChecked();
  expect(errors).toEqual([]);
});
