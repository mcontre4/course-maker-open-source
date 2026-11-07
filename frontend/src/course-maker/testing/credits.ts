import type {
  CheckoutSession,
  CheckoutStatus,
  CreditHistoryPage,
  CreditPack,
  CreditTransaction,
  Credits,
} from "../application/credits";

export const packFixtures: readonly CreditPack[] = [
  {
    id: "pack_small",
    name: "Starter",
    credits: 100,
    bonusCredits: 0,
    priceCents: 500,
    currency: "USD",
    badge: null,
  },
  {
    id: "pack_big",
    name: "Creator",
    credits: 500,
    bonusCredits: 50,
    priceCents: 2000,
    currency: "USD",
    badge: "Most popular",
  },
];

/** Deterministic, inspectable credits port for tests. */
export class MemoryCredits implements Credits {
  credits: number;
  transactions: CreditTransaction[];
  packList: readonly CreditPack[] = packFixtures;
  checkouts: string[] = [];
  statuses: CheckoutStatus[] = [{ status: "paid", creditsAdded: 550 }];
  statusCalls = 0;
  failBalance = false;
  failCheckout = false;
  /** Pages of history, returned in order; the cursor is the page index. */
  pages: readonly (readonly CreditTransaction[])[];

  constructor(credits = 120, transactions: readonly CreditTransaction[] = []) {
    this.credits = credits;
    this.transactions = [...transactions];
    this.pages = [this.transactions];
  }
  async balance() {
    if (this.failBalance) throw new Error("Couldn’t load your credits.");
    return { credits: this.credits };
  }
  async packs() {
    return this.packList;
  }
  async history(cursor?: string): Promise<CreditHistoryPage> {
    const index = cursor ? Number(cursor) : 0;
    return {
      items: this.pages[index] ?? [],
      nextCursor: index + 1 < this.pages.length ? String(index + 1) : null,
    };
  }
  async startCheckout(packId: string): Promise<CheckoutSession> {
    if (this.failCheckout)
      throw new Error("Couldn’t start checkout. You haven’t been charged.");
    this.checkouts.push(packId);
    return { checkoutId: "checkout_1", url: "https://pay.example.test/c/1" };
  }
  async checkoutStatus(): Promise<CheckoutStatus> {
    const status =
      this.statuses[Math.min(this.statusCalls, this.statuses.length - 1)];
    this.statusCalls += 1;
    return status;
  }
}
