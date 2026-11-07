import { Link } from "react-router-dom";
import { creditLevel } from "../application/credits";
import { useAuthentication } from "./authentication";
import { useCreditBalance } from "./credits-context";
import { creditsLabel, formatCredits } from "./credits-format";

export function CoinIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="coin-icon">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5v9M9.6 10.2c.4-.9 1.3-1.4 2.4-1.4 1.4 0 2.4.7 2.4 1.7 0 2.2-4.8 1-4.8 3.2 0 1 1 1.7 2.4 1.7 1.1 0 2-.5 2.4-1.4" />
    </svg>
  );
}

/**
 * Header shortcut showing the learner's balance. It stays out of the way
 * (renders nothing) until the balance is known, if credits are unavailable,
 * or while the learner is signed out.
 */
export function CreditBalanceChip() {
  const auth = useAuthentication();
  if (auth && (auth.loading || !auth.session?.user)) return null;
  return <SignedInCreditBalanceChip />;
}

function SignedInCreditBalanceChip() {
  const balance = useCreditBalance().data;
  if (!balance) return null;
  const level = creditLevel(balance.credits);
  return (
    <Link
      className={"credit-chip credit-chip-" + level}
      to="/credits"
      aria-label={`${creditsLabel(balance.credits)}. Buy more credits`}
    >
      <CoinIcon />
      <span className="credit-chip-amount">
        {formatCredits(balance.credits)}
      </span>
      <span className="credit-chip-plus" aria-hidden="true">
        +
      </span>
    </Link>
  );
}
