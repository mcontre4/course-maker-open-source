import { z } from "zod";
import type {
  CheckoutSession,
  CheckoutStatus,
  CreditBalance,
  CreditHistoryPage,
  CreditPack,
  CreditTransaction,
  Credits,
} from "../../application/credits";
import type { IdGenerator } from "../../application/ports";
import type { KeyValueStorage } from "../persistence/browser-course-repository";

const key = "course-maker:demo-credits:v1";
const pageSize = 20;
const welcomeCredits = 50;

/** Packs the demo storefront sells. The real list comes from the backend. */
export const demoPacks: readonly CreditPack[] = [
  {
    id: "pack_starter",
    name: "Starter",
    credits: 100,
    bonusCredits: 0,
    priceCents: 500,
    currency: "USD",
    badge: null,
  },
  {
    id: "pack_creator",
    name: "Creator",
    credits: 500,
    bonusCredits: 50,
    priceCents: 2000,
    currency: "USD",
    badge: "Most popular",
  },
  {
    id: "pack_studio",
    name: "Studio",
    credits: 1500,
    bonusCredits: 250,
    priceCents: 5000,
    currency: "USD",
    badge: "Best value",
  },
];

const state = z.object({
  credits: z.number().int(),
  transactions: z.array(
    z.object({
      id: z.string(),
      kind: z.enum(["purchase", "usage", "refund", "bonus", "adjustment"]),
      credits: z.number().int(),
      description: z.string(),
      createdAt: z.string(),
    }),
  ),
  pending: z.record(z.string(), z.string()),
  completed: z.record(z.string(), z.number()),
});
type State = z.infer<typeof state>;

/**
 * Browser-only credits for demo mode. "Checkout" skips the payment provider
 * and returns straight to the credits page; the purchase is granted the
 * first time its status is read, as a webhook would.
 */
export class DemoCredits implements Credits {
  constructor(
    private readonly storage: KeyValueStorage,
    private readonly ids: IdGenerator,
    private readonly now: () => Date,
  ) {}

  private read(): State {
    try {
      const raw = this.storage.getItem(key);
      const parsed = state.safeParse(raw ? JSON.parse(raw) : null);
      if (parsed.success) return parsed.data;
    } catch {
      // Fall through to a fresh account.
    }
    const fresh: State = {
      credits: welcomeCredits,
      transactions: [
        {
          id: this.ids.next(),
          kind: "bonus",
          credits: welcomeCredits,
          description: "Welcome credits",
          createdAt: this.now().toISOString(),
        },
      ],
      pending: {},
      completed: {},
    };
    this.write(fresh);
    return fresh;
  }
  private write(next: State) {
    this.storage.setItem(key, JSON.stringify(next));
  }

  async balance(): Promise<CreditBalance> {
    return { credits: this.read().credits };
  }
  async packs() {
    return demoPacks;
  }
  async history(cursor?: string): Promise<CreditHistoryPage> {
    const newestFirst = [...this.read().transactions].reverse();
    const start = cursor ? Number(cursor) || 0 : 0;
    const items = newestFirst.slice(start, start + pageSize);
    const end = start + items.length;
    return {
      items,
      nextCursor: end < newestFirst.length ? String(end) : null,
    };
  }
  async startCheckout(packId: string): Promise<CheckoutSession> {
    if (!demoPacks.some((pack) => pack.id === packId))
      throw new Error("That credit pack is no longer available.");
    const current = this.read();
    const checkoutId = this.ids.next();
    this.write({
      ...current,
      pending: { ...current.pending, [checkoutId]: packId },
    });
    return {
      checkoutId,
      url:
        "/credits?" +
        new URLSearchParams({ checkout: "success", checkout_id: checkoutId }),
    };
  }
  async checkoutStatus(checkoutId: string): Promise<CheckoutStatus> {
    const current = this.read();
    const done = current.completed[checkoutId];
    if (done !== undefined) return { status: "paid", creditsAdded: done };
    const pack = demoPacks.find((p) => p.id === current.pending[checkoutId]);
    if (!pack) return { status: "expired", creditsAdded: 0 };
    const added = pack.credits + pack.bonusCredits;
    const { [checkoutId]: _paid, ...pending } = current.pending;
    const purchase: CreditTransaction = {
      id: this.ids.next(),
      kind: "purchase",
      credits: added,
      description: `${pack.name} pack`,
      createdAt: this.now().toISOString(),
    };
    this.write({
      credits: current.credits + added,
      transactions: [...current.transactions, purchase],
      pending,
      completed: { ...current.completed, [checkoutId]: added },
    });
    return { status: "paid", creditsAdded: added };
  }
}
