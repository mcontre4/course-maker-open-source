import { expect, it } from "vitest";
import { HttpCredits } from "./credits";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

it("reads the balance, packs and activity from the credits endpoints", async () => {
  const requests: { url: string; method?: string; body?: unknown }[] = [];
  const credits = new HttpCredits(async (url, init) => {
    requests.push({
      url,
      method: init?.method,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    if (url.endsWith("/packs"))
      return json({
        packs: [
          {
            id: "pack_a",
            name: "Starter",
            credits: 100,
            bonusCredits: 10,
            priceCents: 500,
            currency: "USD",
            badge: null,
          },
        ],
      });
    if (url.includes("/transactions"))
      return json({
        items: [
          {
            id: "t1",
            kind: "usage",
            credits: -12,
            description: "Lesson: Tides",
            createdAt: "2026-11-01T10:00:00Z",
          },
        ],
        nextCursor: "c2",
      });
    return json({ credits: 42 });
  });
  expect(await credits.balance()).toEqual({ credits: 42 });
  expect((await credits.packs())[0].bonusCredits).toBe(10);
  const page = await credits.history("c1");
  expect(page.nextCursor).toBe("c2");
  expect(requests.map((r) => r.url)).toEqual([
    "/api/v1/credits",
    "/api/v1/credits/packs",
    "/api/v1/credits/transactions?limit=20&cursor=c1",
  ]);
});

it("starts a checkout with only the pack id and reads its status", async () => {
  const requests: { url: string; method?: string; body?: unknown }[] = [];
  const credits = new HttpCredits(async (url, init) => {
    requests.push({
      url,
      method: init?.method,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    return url.endsWith("/checkout")
      ? json({ checkoutId: "chk_1", url: "https://pay.example.test/chk_1" })
      : json({ status: "paid", creditsAdded: 110 });
  });
  expect(await credits.startCheckout("pack_a")).toEqual({
    checkoutId: "chk_1",
    url: "https://pay.example.test/chk_1",
  });
  expect(await credits.checkoutStatus("chk 1")).toEqual({
    status: "paid",
    creditsAdded: 110,
  });
  expect(requests).toEqual([
    {
      url: "/api/v1/credits/checkout",
      method: "POST",
      body: { packId: "pack_a" },
    },
    { url: "/api/v1/credits/checkout/chk%201", method: "GET", body: undefined },
  ]);
});

it("refuses to send the browser to a script or protocol-relative checkout URL", async () => {
  for (const url of ["javascript:alert(1)", "//evil.example/pay"]) {
    const credits = new HttpCredits(async () =>
      json({ checkoutId: "chk_1", url }),
    );
    await expect(credits.startCheckout("pack_a")).rejects.toThrow(
      "Unexpected credits response",
    );
  }
});

it("surfaces server messages with the HTTP status, and rejects malformed data", async () => {
  const refused = new HttpCredits(async () =>
    json({ detail: "Payments are paused." }, 503),
  );
  await expect(refused.startCheckout("pack_a")).rejects.toMatchObject({
    message: "Payments are paused.",
    status: 503,
  });
  const offline = new HttpCredits(async () => {
    throw new TypeError("network");
  });
  await expect(offline.balance()).rejects.toThrow(
    "Couldn’t load your credits.",
  );
  const malformed = new HttpCredits(async () => json({ credits: "many" }));
  await expect(malformed.balance()).rejects.toThrow(
    "Unexpected credits response",
  );
});
