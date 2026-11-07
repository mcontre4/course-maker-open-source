import { test, expect, type Locator, type Page } from "@playwright/test";

/** Nothing on the page may be wider than the screen. */
async function expectNoSidewaysScroll(page: Page) {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

async function expectInsideScreen(target: Locator) {
  const box = await target.boundingBox();
  const size = target.page().viewportSize();
  expect(box).not.toBeNull();
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.y + box!.height).toBeLessThanOrEqual(size!.height);
}

test.describe("Phone navigation", () => {
  test("main destinations stay in a tab bar under the thumb", async ({
    page,
  }) => {
    await page.goto("/explore");
    await expect(page.locator(".explore-hero h1")).toBeVisible();
    await expectNoSidewaysScroll(page);
    const tabs = [
      page.getByRole("link", { name: "My learning" }),
      page.locator(".explore-navigation > summary"),
      page.getByRole("button", { name: "Open search" }),
      page.locator(".create-menu > summary"),
    ];
    await page.evaluate(() => window.scrollTo(0, 400));
    const screen = page.viewportSize()!;
    for (const tab of tabs) {
      await expectInsideScreen(tab);
      const box = (await tab.boundingBox())!;
      expect(box.y).toBeGreaterThan(screen.height * 0.8);
      expect(box.height).toBeGreaterThanOrEqual(44);
    }
  });

  test("Explore opens as a sheet whose links work with one tap", async ({
    page,
  }) => {
    await page.goto("/");
    const explore = page.locator(".explore-navigation > summary");
    await explore.tap();
    const sheet = page.locator(".explore-panel");
    await expect(sheet).toBeVisible();
    await expectInsideScreen(sheet);
    await page.getByRole("button", { name: "Close Explore menu" }).tap();
    await expect(sheet).toBeHidden();

    await explore.tap();
    await sheet.getByRole("link", { name: "Thermodynamics" }).tap();
    await expect(page).toHaveURL(/\/explore\/engineering\?sub=Thermodynamics/);
    await expect(sheet).toBeHidden();
  });

  test("tapping the scrim dismisses a sheet without activating the page", async ({
    page,
  }) => {
    await page.goto("/explore");
    await page.locator(".explore-navigation > summary").tap();
    await expect(page.locator(".explore-panel")).toBeVisible();
    await page.touchscreen.tap(page.viewportSize()!.width / 2, 30);
    await expect(page.locator(".explore-panel")).toBeHidden();
    await expect(page).toHaveURL(/\/explore$/);
  });

  test("search takes the whole screen and a suggestion opens with one tap", async ({
    page,
  }) => {
    await page.goto("/explore");
    await page.getByRole("button", { name: "Open search" }).tap();
    const input = page.getByRole("combobox");
    await expect(input).toBeFocused();
    const fontSize = await input.evaluate(
      (node) => getComputedStyle(node).fontSize,
    );
    // Anything smaller makes iOS zoom the page on focus.
    expect(parseFloat(fontSize)).toBeGreaterThanOrEqual(16);
    await expect(
      page
        .getByRole("navigation", { name: "Browse by topic" })
        .getByRole("link", { name: "Engineering" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).tap();
    await expect(input).toBeHidden();
    await expect(
      page.getByRole("button", { name: "Open search" }),
    ).toBeFocused();

    await page.getByRole("button", { name: "Open search" }).tap();
    await input.fill("Newest public");
    const suggestion = page
      .getByRole("option", { name: /Newest public lesson/ })
      .first();
    await suggestion.tap();
    await expect(page).not.toHaveURL(/\/explore/);
    await expect(input).toBeHidden();
  });

  test("the tab bar makes way for the keyboard", async ({ page }) => {
    await page.goto("/workspace");
    const tab = page.getByRole("link", { name: "My learning" });
    await expect(tab).toBeVisible();
    await page.getByRole("searchbox").first().focus();
    await expect(tab).toBeHidden();
  });

  test("a lesson opens with its video first, across the full width", async ({
    page,
    request,
  }) => {
    const latest = await (
      await request.get("/api/v1/published/discovery")
    ).json();
    await page.goto(`/watch/lessons/${latest.lessons[0].id}`);
    const video = page.locator("video");
    await expect(video).toBeVisible();
    const box = (await video.boundingBox())!;
    const heading = (await page.locator(".watch-page h1").boundingBox())!;
    expect(box.width).toBe(page.viewportSize()!.width);
    expect(box.y).toBeLessThan(heading.y);
    await expectNoSidewaysScroll(page);
  });
});
