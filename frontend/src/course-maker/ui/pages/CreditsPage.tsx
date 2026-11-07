import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import {
  creditLevel,
  packTotalCredits,
  type CreditPack,
  type CreditTransaction,
} from "../../application/credits";
import { useApplication } from "../application-context";
import { CoinIcon } from "../CreditBalance";
import {
  useCheckoutStatus,
  useCreditBalance,
  useCreditHistory,
  useCreditPacks,
  useRefreshCredits,
  useStartCheckout,
} from "../credits-context";
import {
  creditsLabel,
  formatActivityDate,
  formatCredits,
  formatPerCredit,
  formatPrice,
  formatSigned,
} from "../credits-format";
import { ErrorNotice, PageHeading, QueryStatus } from "../components";
import { Button } from "../primitives/Button";

export function CreditsPage() {
  const available = !!useApplication().credits;
  return (
    <>
      <PageHeading eyebrow="YOUR ACCOUNT" title="Credits">
        Credits are what you spend to bring your lessons to life. Top up
        whenever you need more.
      </PageHeading>
      {available ? (
        <div className="credits-layout">
          <CheckoutResult />
          <BalanceCard />
          <PackPicker />
          <ActivityList />
        </div>
      ) : (
        <div className="status-panel" role="status">
          <h2>Credits aren’t available yet.</h2>
          <p className="muted">
            Connect to the server to see your balance and buy credits.
          </p>
        </div>
      )}
    </>
  );
}

/* ---------- Returning from the payment page ---------- */

function CheckoutResult() {
  const [params, setParams] = useSearchParams();
  const outcome = params.get("checkout");
  const checkoutId = params.get("checkout_id");
  const status = useCheckoutStatus(outcome === "success" ? checkoutId : null);
  const refresh = useRefreshCredits();
  const refreshed = useRef<string | null>(null);
  const paid = status.data?.status === "paid";
  useEffect(() => {
    if (paid && refreshed.current !== checkoutId) {
      refreshed.current = checkoutId;
      void refresh();
    }
  });
  const dismiss = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete("checkout");
        next.delete("checkout_id");
        return next;
      },
      { replace: true },
    );

  if (outcome === "cancelled")
    return (
      <Notice tone="neutral" title="Checkout cancelled" onDismiss={dismiss}>
        You weren’t charged. Pick a pack below whenever you’re ready.
      </Notice>
    );
  if (outcome !== "success") return null;
  if (!checkoutId)
    return (
      <Notice
        tone="neutral"
        title="Thanks for your purchase"
        onDismiss={dismiss}
      >
        Your credits will show up here as soon as the payment clears.
      </Notice>
    );
  if (status.error)
    return (
      <Notice tone="error" title="We couldn’t confirm your payment yet">
        <ErrorNotice error={status.error} />
        <Button variant="secondary" onClick={() => void status.refetch()}>
          Check again
        </Button>
      </Notice>
    );
  const result = status.data;
  if (!result)
    return (
      <Notice tone="neutral" title="Confirming your payment…" busy>
        This usually takes a few seconds.
      </Notice>
    );
  if (result.status === "paid")
    return (
      <Notice tone="success" title="Payment received" onDismiss={dismiss}>
        {result.creditsAdded > 0
          ? `${creditsLabel(result.creditsAdded)} added to your balance.`
          : "Your credits were already added to your balance."}
      </Notice>
    );
  if (result.status === "failed")
    return (
      <Notice
        tone="error"
        title="The payment didn’t go through"
        onDismiss={dismiss}
      >
        You haven’t been charged. Try again or use a different payment method.
      </Notice>
    );
  if (result.status === "expired")
    return (
      <Notice tone="neutral" title="That checkout expired" onDismiss={dismiss}>
        You haven’t been charged. Start a new purchase below.
      </Notice>
    );
  return status.gaveUp ? (
    <Notice
      tone="neutral"
      title="Still processing your payment"
      onDismiss={dismiss}
    >
      Your credits will appear here as soon as the payment clears. You can
      safely leave this page.
    </Notice>
  ) : (
    <Notice tone="neutral" title="Confirming your payment…" busy>
      This usually takes a few seconds.
    </Notice>
  );
}

function Notice({
  tone,
  title,
  busy = false,
  onDismiss,
  children,
}: {
  tone: "success" | "neutral" | "error";
  title: string;
  busy?: boolean;
  onDismiss?: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className={"credits-notice credits-notice-" + tone}
      role={tone === "error" ? "alert" : "status"}
      aria-busy={busy || undefined}
    >
      <div>
        <strong>{title}</strong>
        <div className="credits-notice-body">{children}</div>
      </div>
      {onDismiss ? (
        <button
          type="button"
          className="text-button"
          aria-label="Dismiss message"
          onClick={onDismiss}
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}

/* ---------- Balance ---------- */

function BalanceCard() {
  const query = useCreditBalance();
  if (query.isPending)
    return (
      <section
        className="credit-balance-card"
        aria-busy="true"
        aria-label="Your balance"
      >
        <p className="muted">Loading your balance…</p>
      </section>
    );
  if (!query.data)
    return (
      <section className="credit-balance-card" aria-label="Your balance">
        <ErrorNotice error={query.error} />
        <Button variant="secondary" onClick={() => void query.refetch()}>
          Try again
        </Button>
      </section>
    );
  const credits = query.data.credits;
  const level = creditLevel(credits);
  return (
    <section
      className={"credit-balance-card credit-balance-" + level}
      aria-labelledby="credit-balance-label"
    >
      <span className="credit-balance-icon">
        <CoinIcon />
      </span>
      <div>
        <p className="eyebrow muted" id="credit-balance-label">
          YOUR BALANCE
        </p>
        <p className="credit-balance-value">
          <strong>{formatCredits(credits)}</strong>
          <span>{credits === 1 ? "credit" : "credits"}</span>
        </p>
      </div>
      <p className="credit-balance-hint">
        {level === "empty"
          ? "You’re out of credits. Add some to keep creating."
          : level === "low"
            ? "Running low — top up so your next lesson isn’t interrupted."
            : "You’re all set to create."}
      </p>
    </section>
  );
}

/* ---------- Buying ---------- */

function PackPicker() {
  const query = useCreditPacks();
  const checkout = useStartCheckout();
  const resetCheckout = checkout.reset;
  useEffect(() => {
    // Returning with the browser's Back button can restore this page frozen
    // mid-redirect; let the learner try again instead of a stuck button.
    const restored = (event: PageTransitionEvent) => {
      if (event.persisted) resetCheckout();
    };
    window.addEventListener("pageshow", restored);
    return () => window.removeEventListener("pageshow", restored);
  }, [resetCheckout]);
  const [chosen, setChosen] = useState<string | null>(null);
  if (!query.data)
    return (
      <section className="credits-section" aria-labelledby="buy-heading">
        <h2 id="buy-heading">Buy credits</h2>
        {query.isPending ? (
          <p className="muted" role="status">
            Loading packs…
          </p>
        ) : (
          <QueryStatus
            pending={false}
            error={query.error}
            retry={() => void query.refetch()}
          />
        )}
      </section>
    );
  const packs = query.data;
  const selected: CreditPack | undefined =
    packs.find((pack) => pack.id === chosen) ??
    packs.find((pack) => pack.badge) ??
    packs[0];
  const redirecting = checkout.isSuccess;
  return (
    <section className="credits-section" aria-labelledby="buy-heading">
      <h2 id="buy-heading">Buy credits</h2>
      {packs.length === 0 ? (
        <p className="muted">No credit packs are available right now.</p>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (selected) checkout.mutate(selected.id);
          }}
        >
          <fieldset
            className="credit-packs"
            disabled={checkout.isPending || redirecting}
          >
            <legend className="sr-only">Choose a credit pack</legend>
            {packs.map((pack) => (
              <PackOption
                key={pack.id}
                pack={pack}
                selected={pack.id === selected?.id}
                onSelect={() => setChosen(pack.id)}
              />
            ))}
          </fieldset>
          <div className="credits-checkout">
            <p className="muted small">
              You’ll finish paying on our payment provider’s secure page. We
              never see or store your card details.
            </p>
            <ErrorNotice error={checkout.error} />
            <Button
              type="submit"
              disabled={!selected || checkout.isPending || redirecting}
            >
              {redirecting
                ? "Taking you to checkout…"
                : checkout.isPending
                  ? "Starting checkout…"
                  : selected
                    ? `Buy ${creditsLabel(packTotalCredits(selected))} · ${formatPrice(selected.priceCents, selected.currency)}`
                    : "Buy credits"}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

function PackOption({
  pack,
  selected,
  onSelect,
}: {
  pack: CreditPack;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <label className={"credit-pack" + (selected ? " is-selected" : "")}>
      <input
        type="radio"
        name="credit-pack"
        className="sr-only"
        checked={selected}
        onChange={onSelect}
      />
      {pack.badge ? (
        <span className="credit-pack-badge">{pack.badge}</span>
      ) : null}
      <span className="credit-pack-name">{pack.name}</span>
      <span className="credit-pack-credits">
        <strong>{formatCredits(packTotalCredits(pack))}</strong> credits
      </span>
      {pack.bonusCredits > 0 ? (
        <span className="credit-pack-bonus">
          Includes {formatCredits(pack.bonusCredits)} bonus
        </span>
      ) : (
        <span className="credit-pack-bonus" aria-hidden="true">
          &nbsp;
        </span>
      )}
      <span className="credit-pack-price">
        {formatPrice(pack.priceCents, pack.currency)}
      </span>
      <span className="credit-pack-rate muted small">
        {formatPerCredit(pack)}
      </span>
    </label>
  );
}

/* ---------- Activity ---------- */

const kindLabel: Readonly<Record<CreditTransaction["kind"], string>> = {
  purchase: "Purchase",
  usage: "Used",
  refund: "Refund",
  bonus: "Bonus",
  adjustment: "Adjustment",
};

function ActivityList() {
  const query = useCreditHistory();
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section className="credits-section" aria-labelledby="activity-heading">
      <h2 id="activity-heading">Activity</h2>
      {query.isPending ? (
        <p className="muted" role="status">
          Loading activity…
        </p>
      ) : query.error && items.length === 0 ? (
        <>
          <ErrorNotice error={query.error} />
          <Button variant="secondary" onClick={() => void query.refetch()}>
            Try again
          </Button>
        </>
      ) : items.length === 0 ? (
        <p className="muted">
          Nothing here yet. Your purchases and what you spend will show up here.
        </p>
      ) : (
        <>
          <ul className="credit-activity">
            {items.map((item) => (
              <li key={item.id}>
                <span className={"credit-kind credit-kind-" + item.kind}>
                  {kindLabel[item.kind]}
                </span>
                <span className="credit-activity-text">
                  <strong>{item.description}</strong>
                  <time className="muted small" dateTime={item.createdAt}>
                    {formatActivityDate(item.createdAt)}
                  </time>
                </span>
                <span
                  className={
                    "credit-delta " +
                    (item.credits >= 0 ? "credit-delta-in" : "credit-delta-out")
                  }
                >
                  {formatSigned(item.credits)}
                  <span className="sr-only">
                    {Math.abs(item.credits) === 1 ? " credit" : " credits"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          {query.error ? <ErrorNotice error={query.error} /> : null}
          {query.hasNextPage ? (
            <Button
              variant="secondary"
              disabled={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {query.isFetchingNextPage ? "Loading…" : "Show more"}
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}
