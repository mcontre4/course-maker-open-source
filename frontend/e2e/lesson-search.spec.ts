import { test, expect } from "@playwright/test";

test.skip(
  process.env.VITE_COURSE_CREATION !== "false",
  "Exercises lessons-only mode",
);
test.use({
  extraHTTPHeaders: {
    "x-test-owner": "user_00000000-0000-0000-0000-000000000002",
  },
});

for (const viewport of [
  { width: 1280, height: 900 },
  { width: 390, height: 844 },
]) {
  test.describe(`lesson search at ${viewport.width}px`, () => {
    test.use({ viewport });
    test("keeps header search and full results available with course features disabled", async ({
      page,
    }) => {
      const errors: string[] = [];
      const courseRequests: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("request", (request) => {
        if (new URL(request.url()).pathname === "/api/v1/courses")
          courseRequests.push(request.url());
      });
      await page.goto("/explore");
      const input = page.getByRole("combobox", {
        name: "Search lessons",
        exact: true,
      });
      await expect(input).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "All lessons", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("navigation", { name: "Topics", exact: true }),
      ).toBeVisible();
      await page.getByText("Explore", { exact: true }).click();
      await expect(
        page
          .locator(".explore-panel")
          .getByRole("link", { name: "Computer science" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
      await input.fill("NEWEST public");
      const option = page.getByRole("option", {
        name: "Newest public lesson Lesson · Published",
      });
      await expect(option).toBeVisible();
      await expect(
        page.getByRole("listbox", { name: "Lesson suggestions" }),
      ).not.toContainText("Newest public course");
      await page.screenshot({
        path: test.info().outputPath("lesson-search.png"),
      });
      await page
        .getByRole("link", { name: "View all results for “NEWEST public” →" })
        .click();
      const results = page.getByRole("region", {
        name: "Find lessons",
        exact: true,
      });
      await expect(
        results.getByRole("link", { name: /Newest public lesson/ }),
      ).toBeVisible();
      await expect(results).not.toContainText("course");
      await page.reload();
      await expect(input).toHaveValue("NEWEST public");
      await expect(
        results.getByRole("link", { name: /Newest public lesson/ }),
      ).toBeVisible();
      await input.fill("nothing-matches-this");
      await expect(page.getByRole("search")).toContainText("No lessons found.");
      await input.fill("newest public les");
      await option.click();
      await expect(page).toHaveURL(/\/watch\/lessons\/lesson_/);
      await expect(
        page.getByRole("heading", {
          name: "Newest public lesson",
          exact: true,
        }),
      ).toBeVisible();
      await expect
        .poll(() =>
          page
            .locator("video")
            .evaluate((video: HTMLVideoElement) => video.readyState),
        )
        .toBeGreaterThanOrEqual(2);
      expect(courseRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}
