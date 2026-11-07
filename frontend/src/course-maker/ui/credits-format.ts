import type { CreditPack } from "../application/credits";
import { packTotalCredits } from "../application/credits";

const number = new Intl.NumberFormat("en-US");

export function formatCredits(credits: number): string {
  return number.format(credits);
}

export function creditsLabel(credits: number): string {
  return `${formatCredits(credits)} ${Math.abs(credits) === 1 ? "credit" : "credits"}`;
}

export function formatSigned(credits: number): string {
  return (
    (credits > 0 ? "+" : credits < 0 ? "−" : "") +
    formatCredits(Math.abs(credits))
  );
}

export function formatPrice(cents: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(cents / 100);
}

export function formatPerCredit(pack: CreditPack): string {
  return (
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: pack.currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 3,
    }).format(pack.priceCents / 100 / packTotalCredits(pack)) + " per credit"
  );
}

export function formatActivityDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
