import { test, expect } from "@playwright/test";

const owner = "user_00000000-0000-0000-0000-000000000001";

test("newest finished content is discoverable and publicly playable", async ({
  page,
  browser,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/explore");
  const lessons = page.getByRole("region", { name: "Newest lessons" });
  const courses = page.getByRole("main");
  const latest = await (
    await request.get("/api/v1/published/discovery")
  ).json();
  await expect(lessons.getByRole("heading").nth(1)).toHaveText(
    latest.lessons[0].title,
  );
  await expect(
    courses.getByRole("heading", { name: "Newest public course" }),
  ).toBeVisible();
  await expect(lessons).not.toContainText("Unfinished hidden lesson");
  await expect(courses).not.toContainText("Unfinished hidden course");
  await lessons
    .getByRole("link")
    .filter({
      has: page.getByRole("heading", {
        name: "Newest public lesson",
        exact: true,
      }),
    })
    .click();
  const video = page.locator("video");
  await expect(video).toHaveAttribute(
    "src",
    /\/published\/lessons\/.*\/video$/,
  );
  await expect
    .poll(() => video.evaluate((node: HTMLVideoElement) => node.readyState))
    .toBeGreaterThanOrEqual(2);
  await video.evaluate((node: HTMLVideoElement) => node.play());
  await expect
    .poll(() => video.evaluate((node: HTMLVideoElement) => node.currentTime))
    .toBeGreaterThan(0);
  await page.getByRole("link", { name: /Created by/ }).click();
  await expect(page).toHaveURL(new RegExp(`/creators/${owner}`));
  await expect(
    page.getByRole("region", { name: "Lessons", exact: true }),
  ).toContainText("Newest public lesson");
  await expect(
    page.getByRole("region", { name: "Courses", exact: true }),
  ).toContainText("Newest public course");

  // A clean browser has no creator cookie or local storage.
  const visitor = await browser.newContext();
  const publicPage = await visitor.newPage();
  await publicPage.goto(`/creators/${owner}`);
  const course = publicPage.getByRole("region", {
    name: "Courses",
    exact: true,
  });
  await course.getByRole("link", { name: "Start course" }).first().click();
  await expect(publicPage.locator("video")).toHaveAttribute(
    "src",
    /course_id=course_/,
  );
  await expect
    .poll(() =>
      publicPage
        .locator("video")
        .evaluate((node: HTMLVideoElement) => node.readyState),
    )
    .toBeGreaterThanOrEqual(2);
  await publicPage.goto("/explore");
  await publicPage
    .getByRole("main")
    .getByRole("link", { name: "Start course →" })
    .first()
    .click();
  await expect(
    publicPage.getByRole("navigation", { name: "Course lessons" }),
  ).toBeVisible();
  await visitor.close();
  expect(errors).toEqual([]);
});
