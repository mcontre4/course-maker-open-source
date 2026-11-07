import { z } from "zod";
import type {
  CheckoutSession,
  CheckoutStatus,
  CreditBalance,
  CreditHistoryPage,
  CreditPack,
  Credits,
} from "../../application/credits";
import type { HttpTransport } from "./course-backend";

const balance = z.object({ credits: z.number().int() });
const pack = z.object({
  id: z.string(),
  name: z.string(),
  credits: z.number().int().positive(),
  bonusCredits: z.number().int().nonnegative(),
  priceCents: z.number().int().nonnegative(),
  currency: z.string().length(3),
  badge: z.string().nullable(),
});
const transaction = z.object({
  id: z.string(),
  kind: z.enum(["purchase", "usage", "refund", "bonus", "adjustment"]),
  credits: z.number().int(),
  description: z.string(),
  createdAt: z.string(),
});
const history = z.object({
  items: z.array(transaction),
  nextCursor: z.string().nullable(),
});
// The browser is sent to this URL, so never accept script or protocol-relative URLs.
const checkoutUrl = z.string().regex(/^(https?:\/\/|\/(?!\/))/);
const checkoutSession = z.object({ checkoutId: z.string(), url: checkoutUrl });
const checkoutStatus = z.object({
  status: z.enum(["pending", "paid", "failed", "expired"]),
  creditsAdded: z.number().int().nonnegative(),
});

export class HttpCredits implements Credits {
  constructor(private readonly transport: HttpTransport) {}

  private async request<T>(
    schema: z.ZodType<T>,
    path: string,
    failure: string,
    body?: unknown,
  ): Promise<T> {
    let response: Response;
    try {
      response = await this.transport("/api/v1/credits" + path, {
        method: body === undefined ? "GET" : "POST",
        credentials: "same-origin",
        headers:
          body === undefined
            ? undefined
            : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new Error(failure);
    }
    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? data.detail
          : null;
      throw Object.assign(
        new Error(typeof detail === "string" ? detail : failure),
        { status: response.status },
      );
    }
    const parsed = schema.safeParse(data);
    if (!parsed.success)
      throw new Error("Unexpected credits response. Please try again.");
    return parsed.data;
  }

  balance(): Promise<CreditBalance> {
    return this.request(balance, "", "Couldn’t load your credits.");
  }
  async packs(): Promise<readonly CreditPack[]> {
    const result = await this.request(
      z.object({ packs: z.array(pack) }),
      "/packs",
      "Couldn’t load credit packs.",
    );
    return result.packs;
  }
  history(cursor?: string): Promise<CreditHistoryPage> {
    const query = new URLSearchParams({ limit: "20" });
    if (cursor) query.set("cursor", cursor);
    return this.request(
      history,
      "/transactions?" + query,
      "Couldn’t load your credit activity.",
    );
  }
  startCheckout(packId: string): Promise<CheckoutSession> {
    return this.request(
      checkoutSession,
      "/checkout",
      "Couldn’t start checkout. You haven’t been charged.",
      { packId },
    );
  }
  checkoutStatus(checkoutId: string): Promise<CheckoutStatus> {
    return this.request(
      checkoutStatus,
      "/checkout/" + encodeURIComponent(checkoutId),
      "Couldn’t confirm your purchase yet.",
    );
  }
}
