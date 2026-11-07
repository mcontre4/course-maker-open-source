import { test, expect } from "@playwright/test";

test("course guide uses the same rich answer renderer and persists its own chat", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const created = await request.post("/api/v1/courses", {
    data: {
      style: { visualStyleId: "flat-vector-science" },
      title: "Bond chemistry",
      description: "Learn about bonds",
      duration: { mode: "total", hours: 2 },
    },
  });
  expect(created.ok()).toBeTruthy();
  const course = await created.json();
  await page.goto(`/courses/${course.id}/syllabus`);
  const box = page.getByRole("textbox", { name: "Message your course guide" });
  await expect(box).toBeEnabled();
  await box.fill("Explain bonds visually");
  await box.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Understanding bonds" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Ionic");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Understanding bonds" }),
  ).toBeVisible();
  await expect(box).toBeEnabled();
  await page
    .getByRole("heading", { name: "Understanding bonds" })
    .scrollIntoViewIfNeeded();
  await page
    .getByRole("complementary", { name: "Chat with your guide" })
    .screenshot({ path: "test-results/course-guide-desktop.png" });
  expect(errors).toEqual([]);
});

test("lesson guide renders rich answers, reopens history, switches roles and recovers malformed UI", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  const failedRequests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400)
      failedRequests.push(`${response.status()} ${response.url()}`);
  });
  const created = await request.post("/api/v1/lessons", {
    data: {
      style: { visualStyleId: "flat-vector-science" },
      title: "Chemical bonds",
      description: "Explain bonds",
      minutes: 3,
    },
  });
  expect(created.ok()).toBeTruthy();
  const lesson = await created.json();
  const plan = await request.post(`/api/v1/lessons/${lesson.id}/plan`, {
    data: { expectedRevision: 0, message: "Generate the first outline" },
  });
  expect(plan.ok()).toBeTruthy();
  await page.goto(`/lessons/${lesson.id}?edit=1`);
  const box = page.getByRole("textbox", { name: "Message your lesson guide" });
  await expect(box).toBeEnabled();
  await box.fill("Explain bonds visually");
  await box.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Understanding bonds" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Covalent");
  await expect(box).toHaveValue("");
  const chatUrl = page.url();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Understanding bonds" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Understanding bonds" }),
  ).toHaveCount(0);
  await expect(box).toBeEnabled();
  await box.fill("Explain bonds in Markdown");
  await page.getByRole("button", { name: "Send message ↑" }).click();
  await expect(
    page.getByRole("heading", { name: "Bond basics" }),
  ).toBeVisible();
  await expect(box).toBeEnabled();
  await box.fill("Show malformed UI");
  await box.press("Enter");
  await expect(
    page.getByText(/This answer could not be displayed/),
  ).toBeVisible();
  await expect(box).toBeEnabled();
  await page.getByText("Chat settings & saved context").click();
  for (const role of ["storyboard", "animation"]) {
    await page.getByLabel("Guide focus").selectOption(role);
    await expect(
      page.getByRole("heading", { name: "Bond basics" }),
    ).toHaveCount(0);
    await expect(box).toBeEnabled();
    await box.fill("Explain bonds visually");
    await box.press("Enter");
    await expect(
      page.getByRole("heading", { name: "Understanding bonds" }),
    ).toBeVisible();
    await expect(box).toBeEnabled();
  }
  await page.goto(chatUrl);
  await expect(
    page.getByRole("heading", { name: "Understanding bonds" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(box).toBeVisible();
  await page
    .getByRole("heading", { name: "Understanding bonds" })
    .scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("complementary", { name: "Chat with your guide" })
    .screenshot({
      path: "test-results/lesson-guide-mobile.png",
    });
  expect(errors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
