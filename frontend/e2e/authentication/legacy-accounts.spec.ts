import { test, expect } from "@playwright/test";
import { createHmac } from "node:crypto";

test("legacy checkout credits the wallet through a signed webhook and survives reload", async ({
  page,
}) => {
  await page.route("https://checkout.stripe.com/c/pay/**", async (route) => {
    const checkoutId = route.request().url().split("/").at(-1)!;
    const result = new URL("http://127.0.0.1:5182/credits");
    result.searchParams.set("checkout", "success");
    result.searchParams.set("checkout_id", checkoutId);
    await route.fulfill({
      contentType: "text/html",
      body: `<h1>Test Stripe checkout</h1><a href="${result}">Return to Course Maker</a>`,
    });
  });
  await page.goto("/credits");
  const balance = page.getByRole("region", { name: /your balance/i });
  await expect(balance.getByText("0", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: /Creator/ }).check();
  const checkoutResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/credits/checkout") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Buy 550 credits/ }).click();
  expect((await checkoutResponse).status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Test Stripe checkout" }),
  ).toBeVisible();
  const checkoutId = new URL(page.url()).pathname.split("/").at(-1)!;
  // Stripe's server-to-server webhook is the only action that grants the purchase.
  const payload = JSON.stringify({
    type: "checkout.session.completed",
    data: {
      object: {
        id: "cs_test_" + checkoutId,
        metadata: { checkout_id: checkoutId },
        payment_status: "paid",
        amount_total: 2000,
        currency: "usd",
      },
    },
  });
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const digest = createHmac("sha256", "whsec_browser")
    .update(timestamp + "." + payload)
    .digest("hex");
  const deliver = () =>
    page.request.post("http://127.0.0.1:5182/api/v1/credits/webhook", {
      data: payload,
      headers: {
        "Content-Type": "application/json",
        "Stripe-Signature": `t=${timestamp},v1=${digest}`,
      },
    });
  expect((await deliver()).ok()).toBeTruthy();
  await page.getByRole("link", { name: "Return to Course Maker" }).click();
  await expect(balance.getByText("550", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Credit pack purchase (pack_creator)", { exact: true }),
  ).toBeVisible();
  expect((await deliver()).ok()).toBeTruthy();
  await page.reload();
  await expect(balance.getByText("550", { exact: true })).toBeVisible();
  const history = await page.request.get("/api/v1/credits/transactions");
  expect((await history.json()).items).toHaveLength(1);
  await expect(page.getByText("Not found", { exact: true })).toHaveCount(0);
});

test("legacy credits load without account authentication or missing API routes", async ({
  page,
}) => {
  const failedResponses: string[] = [];
  page.on("response", (response) => {
    if (
      response.url().includes("/api/v1/credits") &&
      response.status() >= 400
    ) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  await page.goto("/credits");
  await expect(
    page.getByRole("heading", { name: "Credits", exact: true }),
  ).toBeVisible();
  const balance = page.getByRole("region", { name: /your balance/i });
  await expect(balance.getByText("0", { exact: true })).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(3);
  await expect(
    page.getByRole("heading", { name: "Activity", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Not found", { exact: true })).toHaveCount(0);
  await page.getByText("Starter", { exact: true }).click();
  await expect(page.getByRole("radio", { name: /Starter/ })).toBeChecked();
  await page.reload();
  await expect(balance.getByText("0", { exact: true })).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(3);
  expect(failedResponses).toEqual([]);
});

test("legacy mode keeps the workspace and saved lessons usable without an account", async ({
  page,
}) => {
  const accountRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/auth/") &&
      !request.url().endsWith("/config")
    )
      accountRequests.push(request.url());
  });
  await page.goto("/workspace");
  await expect(
    page.getByRole("heading", { name: "My creations", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL("/workspace");
  await expect(
    page.getByRole("link", { name: "Sign in", exact: true }),
  ).toHaveCount(0);
  const created = await page.request.post("/api/v1/lessons", {
    data: {
      title: "A lesson without an account",
      minutes: 3,
      style: { visualStyleId: "flat-vector-science" },
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "A lesson without an account",
      exact: true,
    }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "A lesson without an account",
      exact: true,
    }),
  ).toBeVisible();
  expect(accountRequests).toEqual([]);
});
