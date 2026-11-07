import { test, expect } from "@playwright/test";

const key = "browser-internal-tools-key-32-characters";

for (const width of [1280, 390]) {
  test(`internal lesson diagnostics at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const discovery = await (
      await request.get("/api/v1/published/discovery")
    ).json();
    const lesson = discovery.lessons.find(
      (item: { title: string }) => item.title === "Newest public lesson",
    );
    const course = discovery.courses.find(
      (item: { title: string }) => item.title === "Newest public course",
    );
    const endpoint = `/api/v1/internal/lessons/${lesson.id}`;
    expect((await request.get(endpoint)).status()).toBe(403);
    expect((await request.post(endpoint + "/refresh")).status()).toBe(403);
    expect(
      (await request.get(`/api/v1/lessons/${lesson.id}/spend`)).status(),
    ).toBe(403);
    expect(
      (
        await request.post(`/api/v1/lessons/${lesson.id}/spend/refresh`)
      ).status(),
    ).toBe(403);
    expect(
      (await request.get(`/api/v1/courses/${course.id}/spend`)).status(),
    ).toBe(403);
    expect(
      (
        await request.post(`/api/v1/courses/${course.id}/spend/refresh`)
      ).status(),
    ).toBe(403);

    for (const legacy of [
      `/api/v1/lessons/${lesson.id}/spend`,
      `/api/v1/courses/${course.id}/spend`,
    ]) {
      const options = { headers: { "X-Internal-Tools-Key": key } };
      const read = await request.get(legacy, options);
      expect(read.status()).toBe(200);
      expect(read.headers()["cache-control"]).toContain("no-store");
      const refresh = await request.post(legacy + "/refresh", options);
      expect(refresh.status()).toBe(200);
      expect(refresh.headers()["cache-control"]).toContain("no-store");
    }
    await page.goto(`/lessons/${lesson.id}`);
    await expect(
      page.getByRole("heading", { name: "Newest public lesson", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Lesson AI spend")).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Internal tools", exact: true }),
    ).toHaveCount(0);
    await page.goto("/internal/tools");
    await expect(
      page.getByRole("heading", { name: "Internal tools", exact: true }),
    ).toBeVisible();
    const reference = page.getByRole("textbox", { name: "Lesson URL or ID" });
    const access = page.getByLabel("Internal access key");
    await reference.fill(
      new URL(`/watch/lessons/${lesson.id}`, page.url()).href,
    );
    await access.fill("wrong-key");
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Internal access key is invalid.",
    );
    await access.fill(key);
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    const result = page.getByRole("region", {
      name: "Lesson diagnostics result",
    });
    await expect(
      result.getByRole("heading", { name: "Newest public lesson" }),
    ).toBeVisible();
    await expect(result.locator(".internal-metrics")).toContainText("1m 50s");
    const table = result.getByRole("table", { name: "AI spend by step" });
    await expect(table).toBeVisible();
    await expect(
      table.getByRole("rowheader", { name: "Lesson planning" }),
    ).toBeVisible();
    await expect(table).toContainText("fixture-model");
    await expect(table).toContainText("1m 0s");
    const refreshed = page.waitForResponse(
      (response) =>
        response.url().includes("/internal/lessons/") &&
        response.request().method() === "POST",
    );
    await result.getByRole("button", { name: "Refresh spend" }).click();
    expect((await refreshed).status()).toBe(200);
    await expect(result.locator(".internal-metrics")).not.toContainText(
      "pending",
    );
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: test.info().outputPath("internal-tools.png"),
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);

    await reference.fill("lesson_00000000-0000-0000-0000-000000000099");
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    await expect(result).toContainText("Older public lesson");
    await expect(result.locator(".internal-metrics")).toContainText(
      "Unavailable",
    );
    await expect(result).toContainText("No model calls recorded yet.");
    await reference.fill(`/courses/${course.id}/lessons/${lesson.id}`);
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    await expect(table).toContainText("fixture-model");
    await expect(result.locator(".internal-metrics")).toContainText("1m 50s");
    await reference.fill("lesson_00000000-0000-0000-0000-000000000098");
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    await expect(result).toContainText("Unfinished hidden lesson");
    await expect(result.locator(".internal-metrics")).toContainText(
      "In progress",
    );
    const poll = await page.waitForResponse(
      (response) =>
        response
          .url()
          .includes(
            "/internal/lessons/lesson_00000000-0000-0000-0000-000000000098",
          ) && response.request().method() === "GET",
    );
    expect(poll.status()).toBe(200);
    await expect(result).toBeVisible();
    await reference.fill("lesson_00000000-0000-0000-0000-000000009999");
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    await expect(page.getByRole("alert")).toContainText("Lesson not found");
    await expect(result).toHaveCount(0);
    await reference.fill("this is not a lesson");
    await page.getByRole("button", { name: "Inspect lesson" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Enter a lesson URL or lesson ID.",
    );
    expect(errors).toEqual([]);
  });
}
