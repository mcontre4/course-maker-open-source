import { test, expect } from "@playwright/test";

test.describe("Account menu", () => {
  for (const destination of [
    { title: "My library", path: "/library", heading: "My library" },
    { title: "My creations", path: "/workspace", heading: "My creations" },
    { title: "View public profile", path: null, heading: null },
    { title: "Settings", path: "/settings", heading: "Settings" },
  ]) {
    test(`opens ${destination.title} with one activation`, async ({
      page,
      request,
    }, testInfo) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto("/explore");
      const response = await request.get("/api/v1/creators/me");
      expect(response.ok()).toBeTruthy();
      const creator = await response.json();
      const account = page.getByLabel("Account: " + creator.name, {
        exact: true,
      });
      const activate = async (target: typeof account) => {
        if (testInfo.project.use.hasTouch) await target.tap();
        else await target.click();
      };

      await activate(account);
      const link = page
        .locator(".account-panel")
        .getByRole("link", { name: destination.title, exact: true });
      await expect(link).toBeVisible();
      await activate(link);
      await expect(page).toHaveURL(
        destination.path ?? `/creators/${creator.id}`,
      );
      await expect(
        page.getByRole("heading", {
          name: destination.heading ?? creator.name,
          exact: true,
        }),
      ).toBeVisible();
      await expect(page.locator(".account-menu")).not.toHaveAttribute("open");

      // Selecting the current route must also dismiss the menu.
      await activate(account);
      await activate(link);
      await expect(page.locator(".account-menu")).not.toHaveAttribute("open");
      expect(errors).toEqual([]);
    });
  }

  test("dismisses outside and with Escape", async ({ page }, testInfo) => {
    await page.goto("/explore");
    const account = page.getByLabel(/^Account:/);
    const menu = page.locator(".account-menu");
    if (testInfo.project.use.hasTouch) await account.tap();
    else await account.click();
    await expect(menu).toHaveAttribute("open");
    // Blank space outside the disclosure, without navigating away.
    if (testInfo.project.use.hasTouch) await page.touchscreen.tap(1, 1);
    else await page.mouse.click(1, 1);
    await expect(menu).not.toHaveAttribute("open");

    await account.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Escape");
    await expect(menu).not.toHaveAttribute("open");
    await expect(account).toBeFocused();
  });

  test("keeps keyboard navigation inside the menu and closes when tabbing away", async ({
    page,
  }, testInfo) => {
    test.skip(!!testInfo.project.use.hasTouch, "Desktop keyboard navigation");
    await page.goto("/explore");
    const account = page.getByLabel(/^Account:/);
    const menu = page.locator(".account-menu");
    await account.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "View public profile", exact: true }),
    ).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "My library", exact: true }),
    ).toBeFocused();
    await expect(menu).toHaveAttribute("open");
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Shift+Tab");
    await expect(menu).not.toHaveAttribute("open");
  });
});
