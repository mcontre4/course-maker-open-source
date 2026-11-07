import { expect, it } from "vitest";
import { DemoCredits } from "./credits";
import type { KeyValueStorage } from "../persistence/browser-course-repository";

class MemoryStorage implements KeyValueStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}
function demo(storage = new MemoryStorage()) {
  let next = 0;
  return new DemoCredits(
    storage,
    { next: () => "id_" + ++next },
    () => new Date("2026-11-03T12:00:00Z"),
  );
}

it("starts with welcome credits and grants a purchase exactly once", async () => {
  const storage = new MemoryStorage();
  const credits = demo(storage);
  expect(await credits.balance()).toEqual({ credits: 50 });
  const { checkoutId, url } = await credits.startCheckout("pack_creator");
  expect(url).toBe(`/credits?checkout=success&checkout_id=${checkoutId}`);
  expect(await credits.checkoutStatus(checkoutId)).toEqual({
    status: "paid",
    creditsAdded: 550,
  });
  expect(await credits.checkoutStatus(checkoutId)).toEqual({
    status: "paid",
    creditsAdded: 550,
  });
  expect(await demo(storage).balance()).toEqual({ credits: 600 });
  const page = await credits.history();
  expect(page.items.map((item) => item.description)).toEqual([
    "Creator pack",
    "Welcome credits",
  ]);
});

it("rejects unknown packs and expires unknown checkouts", async () => {
  const credits = demo();
  await expect(credits.startCheckout("nope")).rejects.toThrow(
    "no longer available",
  );
  expect(await credits.checkoutStatus("missing")).toEqual({
    status: "expired",
    creditsAdded: 0,
  });
});
