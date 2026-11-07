import { test, expect, type Page } from "@playwright/test";

async function openCourse(page: Page, id: string) {
  const recorded = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/api/v1/learning-activity/" + id),
  );
  await page.goto("/courses/" + id + "/syllabus");
  expect((await recorded).status()).toBe(204);
}

test("the banner follows what was opened last, for the same owner in any browser", async ({
  page,
  browser,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const listed = await (await request.get("/api/v1/courses")).json();
  const ready = listed.items.filter(
    (course: { status: string }) => course.status === "ready",
  );
  expect(ready.length).toBeGreaterThanOrEqual(2);
  const [first, second] = ready as { id: string; title: string }[];

  await openCourse(page, first.id);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "What would you like to learn next?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: first.title, exact: true }),
  ).toContainText("Continue where you left off");

  await openCourse(page, second.id);
  await page.goto("/");
  const banner = page.getByRole("region", { name: second.title, exact: true });
  await expect(banner).toContainText("Continue where you left off");
  await expect(
    page.getByRole("region", { name: "More of your work" }),
  ).toContainText(first.title);

  // This server pins one owner for every browser, standing in for a future login.
  // In production the owner is a per-browser cookie until accounts exist.
  const otherBrowser = await browser.newContext();
  const other = await otherBrowser.newPage();
  await other.goto("/");
  await expect(
    other.getByRole("region", { name: second.title, exact: true }),
  ).toContainText("Continue where you left off");
  await otherBrowser.close();

  expect(errors).toEqual([]);
});

test("the homepage stays within a phone screen", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await page.goto("/");
  await expect(
    page.getByRole("region", { name: "Browse by topic" }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await context.close();
});
