import { test, expect } from "@playwright/test";

test.use({
  extraHTTPHeaders: {
    "x-test-owner": "user_00000000-0000-0000-0000-000000000002",
  },
});

test("typing suggests real lessons and opens public playback with the keyboard", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/explore");
  const search = page.getByRole("combobox", {
    name: "Search courses and lessons",
  });
  const response = page.waitForResponse(
    (response) =>
      response.url().includes("/published/discovery?") &&
      response.url().includes("q=NEWEST+public+lesson"),
  );
  await search.fill("NEWEST public lesson");
  expect((await response).ok()).toBeTruthy();
  const option = page.getByRole("option", {
    name: "Newest public lesson Lesson · Published",
  });
  await expect(option).toBeVisible();
  await expect(page).toHaveURL(/\/explore$/);
  await search.press("ArrowDown");
  await expect(option).toHaveAttribute("aria-selected", "true");
  await search.press("Enter");
  await expect(page).toHaveURL(/\/watch\/lessons\/lesson_/);
  await expect(
    page.getByRole("heading", { name: "Newest public lesson", exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate((video: HTMLVideoElement) => video.readyState),
    )
    .toBeGreaterThanOrEqual(2);
  expect(errors).toEqual([]);
});

test("course suggestions open public courses and all results include lessons after reload", async ({
  page,
}) => {
  await page.goto("/");
  const search = page.getByRole("combobox", {
    name: "Search courses and lessons",
  });
  await search.fill("older public cou");
  await page.getByRole("option", { name: /Older public course/ }).click();
  await expect(page).toHaveURL(/\/watch\/lessons\/lesson_.*\?course=course_/);
  await expect(
    page.getByRole("navigation", { name: "Course lessons" }),
  ).toBeVisible();

  await page.getByRole("combobox").fill("older");
  await page
    .getByRole("link", { name: "View all results for “older” →" })
    .click();
  await expect(page).toHaveURL(/\/explore\?q=older/);
  const results = page.getByRole("region", {
    name: "Find courses and lessons",
  });
  await expect(
    results.getByRole("link", { name: /Older public course/ }),
  ).toBeVisible();
  await expect(
    results.getByRole("link", { name: /Older public lesson/ }),
  ).toBeVisible();
  await page.reload();
  await expect(search).toHaveValue("older");
  await expect(
    results.getByRole("link", { name: /Older public lesson/ }),
  ).toBeVisible();
  await search.fill("nothing-matches-this");
  await expect(page.getByRole("search")).toContainText(
    "No courses or lessons found",
  );
  await search.press("Escape");
  await expect(search).toHaveAttribute("aria-expanded", "false");
  await search.fill("");
  await expect(page.getByRole("listbox")).toHaveCount(0);
});

test("a saved standalone draft is suggested and opens directly", async ({
  page,
  request,
}) => {
  const response = await request.post("/api/v1/lessons", {
    data: {
      title: "Searchable geometry draft",
      description: "A focused geometry lesson",
      minutes: 5,
      style: { visualStyleId: "flat-vector-science" },
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const lesson = await response.json();
  await page.goto("/explore");
  await page.getByRole("combobox").fill("searchable geo");
  await page.getByRole("option", { name: /Searchable geometry draft/ }).click();
  await expect(page).toHaveURL(new RegExp(`/lessons/${lesson.id}$`));
  await expect(
    page.getByRole("heading", {
      name: "Searchable geometry draft",
      exact: true,
    }),
  ).toBeVisible();
});

test("a saved course draft is suggested and opens its syllabus", async ({
  page,
  request,
}) => {
  const response = await request.post("/api/v1/courses", {
    data: {
      title: "Searchable geometry course",
      description: "Learn geometry",
      duration: { mode: "total", hours: 2 },
      style: { visualStyleId: "flat-vector-science" },
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const course = await response.json();
  await page.goto("/explore");
  await page.getByRole("combobox").fill("searchable geometry cou");
  await page
    .getByRole("option", { name: /Searchable geometry course/ })
    .click();
  await expect(page).toHaveURL(new RegExp(`/courses/${course.id}/syllabus$`));
  await expect(
    page.getByRole("heading", {
      name: "Searchable geometry course",
      exact: true,
    }),
  ).toBeVisible();
});
