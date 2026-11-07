/**
 * Credits are the currency learners spend on their creations. They buy packs
 * of credits through a hosted checkout and see a ledger of what changed.
 */
export type CreditBalance = Readonly<{ credits: number }>;

export type CreditPack = Readonly<{
  id: string;
  name: string;
  /** Credits the pack is advertised with, before any bonus. */
  credits: number;
  /** Extra credits granted on top of `credits`. */
  bonusCredits: number;
  /** Price in the currency's minor unit (cents for USD). */
  priceCents: number;
  /** ISO 4217 code, e.g. "USD". */
  currency: string;
  /** Optional marketing label such as "Most popular". */
  badge: string | null;
}>;

export type CreditTransactionKind =
  "purchase" | "usage" | "refund" | "bonus" | "adjustment";

export type CreditTransaction = Readonly<{
  id: string;
  kind: CreditTransactionKind;
  /** Signed: positive adds credits, negative spends them. */
  credits: number;
  description: string;
  /** ISO 8601 timestamp. */
  createdAt: string;
}>;

export type CreditHistoryPage = Readonly<{
  items: readonly CreditTransaction[];
  nextCursor: string | null;
}>;

export type CheckoutSession = Readonly<{
  checkoutId: string;
  /** Where to send the browser to pay. Hosted by the payment provider. */
  url: string;
}>;

export type CheckoutStatus = Readonly<{
  /** `pending` means payment may still complete; credits not added yet. */
  status: "pending" | "paid" | "failed" | "expired";
  creditsAdded: number;
}>;

export interface Credits {
  balance(): Promise<CreditBalance>;
  packs(): Promise<readonly CreditPack[]>;
  history(cursor?: string): Promise<CreditHistoryPage>;
  startCheckout(packId: string): Promise<CheckoutSession>;
  checkoutStatus(checkoutId: string): Promise<CheckoutStatus>;
}

/** HTTP status the backend uses when an action costs more than the balance. */
export const INSUFFICIENT_CREDITS_STATUS = 402;

/** At or below this many credits the UI nudges learners to top up. */
export const LOW_CREDIT_THRESHOLD = 25;

export type CreditLevel = "ok" | "low" | "empty";

export function creditLevel(credits: number): CreditLevel {
  if (credits <= 0) return "empty";
  return credits <= LOW_CREDIT_THRESHOLD ? "low" : "ok";
}

export function packTotalCredits(pack: CreditPack): number {
  return pack.credits + pack.bonusCredits;
}
