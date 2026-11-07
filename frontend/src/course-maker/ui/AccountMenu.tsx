import { useOwnCreator } from "./CreatorLink";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { Avatar, useProfile } from "./profile-context";
import { useAuthentication } from "./authentication";
import { accountPath, isAccountPath } from "./auth-routes";
import { useState } from "react";
import { useApplication } from "./application-context";
import { useCreditBalance } from "./credits-context";
import { creditsLabel } from "./credits-format";
import { SheetClose } from "./SheetClose";

const icons = {
  courses: (
    <>
      <path d="M4 6.5C4 5.7 4.7 5 5.5 5H10c1.1 0 2 .9 2 2v12c0-.8-.7-1.5-1.5-1.5h-5c-.8 0-1.5-.7-1.5-1.5z" />
      <path d="M20 6.5c0-.8-.7-1.5-1.5-1.5H14c-1.1 0-2 .9-2 2v12c0-.8.7-1.5 1.5-1.5h5c.8 0 1.5-.7 1.5-1.5z" />
    </>
  ),
  workspace: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="M8.5 15.5 14 10l1.5 1.5L10 17H8.5z" />
    </>
  ),
  credits: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v8M9.8 10.4c.4-.8 1.2-1.2 2.2-1.2 1.2 0 2.2.6 2.2 1.5 0 2-4.4.9-4.4 2.9 0 .9.9 1.5 2.2 1.5 1 0 1.8-.4 2.2-1.2" />
    </>
  ),
  settings: (
    <>
      <path d="M5 7h8M17 7h2M5 17h2M11 17h8" />
      <circle cx="15" cy="7" r="2" />
      <circle cx="9" cy="17" r="2" />
    </>
  ),
};

function MenuLink({
  to,
  icon,
  title,
  detail,
}: {
  to: string;
  icon: keyof typeof icons;
  title: string;
  detail: ReactNode;
}) {
  const id = useId();
  return (
    <Link
      className="account-link"
      to={to}
      aria-labelledby={id + "-title"}
      aria-describedby={id + "-detail"}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {icons[icon]}
      </svg>
      <span>
        <strong id={id + "-title"}>{title}</strong>
        <span id={id + "-detail"}>{detail}</span>
      </span>
    </Link>
  );
}

export function AccountMenu() {
  const auth = useAuthentication();
  const location = useLocation();
  if (auth?.loading) return <span role="status">Loading account…</span>;
  if (auth && !auth.session?.user) {
    // The sign-in pages already show the form; the header stays quiet there.
    if (isAccountPath(location.pathname)) return null;
    const from = location.pathname + location.search;
    return (
      <>
        <Link className="guest-signin" to={accountPath("/login", from)}>
          Sign in
        </Link>
        <Link
          className="btn btn-secondary guest-signup"
          to={accountPath("/signup", from)}
        >
          Sign up
        </Link>
      </>
    );
  }
  return <AccountMenuDetails auth={auth} />;
}

function AccountMenuDetails({
  auth,
}: {
  auth: ReturnType<typeof useAuthentication>;
}) {
  const { profile: localProfile } = useProfile();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const creatorQuery = useOwnCreator();
  const creator = creatorQuery.data;
  const user = auth?.session?.user;
  const accountProfile = user
    ? {
        ...localProfile,
        email: user.email,
        name: user.first_name + " " + user.last_name,
        picture: null,
      }
    : localProfile;
  const profile = creator
    ? { ...accountProfile, name: creator.name, picture: creator.picture }
    : accountProfile;
  const hasCredits = !!useApplication().credits;
  const balance = useCreditBalance().data;
  const disclosure = useRef<HTMLDetailsElement>(null);
  const id = useId();
  const location = useLocation();
  const close = () => {
    if (disclosure.current) disclosure.current.open = false;
  };
  useEffect(() => {
    if (disclosure.current) disclosure.current.open = false;
  }, [location]);
  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        disclosure.current &&
        !disclosure.current.contains(event.target)
      )
        disclosure.current.open = false;
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);
  if (creatorQuery.isPending && creatorQuery.fetchStatus !== "idle") {
    return <span role="status">Loading account…</span>;
  }
  const identity = (
    <>
      <Avatar name={profile.name} picture={profile.picture} />
      <span>
        <strong>{profile.name}</strong>
        {profile.email ? (
          <span className="muted small">{profile.email}</span>
        ) : null}
        {creator ? (
          <span className="account-identity-hint">View public profile →</span>
        ) : null}
      </span>
    </>
  );
  return (
    <details
      className="account-menu"
      ref={disclosure}
      onBlur={(event) => {
        // Safari touch blurs the summary without focusing the tapped link.
        // Keep it visible until click; outside pointers are handled above.
        if (
          event.relatedTarget &&
          !event.currentTarget.contains(event.relatedTarget)
        )
          event.currentTarget.open = false;
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && disclosure.current) {
          disclosure.current.open = false;
          disclosure.current.querySelector("summary")?.focus();
        }
      }}
    >
      <summary tabIndex={0} aria-label={"Account: " + profile.name}>
        <Avatar name={profile.name} picture={profile.picture} />
        <span className="account-name">{profile.name}</span>
        <span className="chevron" aria-hidden="true" />
      </summary>
      <div className="account-panel">
        <SheetClose label="Close account menu" />
        {creator ? (
          <Link
            className="account-identity"
            to={"/creators/" + creator.id}
            aria-label="View public profile"
            onClick={close}
          >
            {identity}
          </Link>
        ) : (
          <div className="account-identity">{identity}</div>
        )}
        <nav aria-label="Account navigation" onClick={close}>
          <div role="group" aria-labelledby={id + "-learning"}>
            <span
              className="account-group"
              id={id + "-learning"}
              aria-hidden="true"
            >
              Learning
            </span>
            <MenuLink
              to="/library"
              icon="courses"
              title="My library"
              detail="Lessons to learn from"
            />
          </div>
          <div role="group" aria-labelledby={id + "-creating"}>
            <span
              className="account-group"
              id={id + "-creating"}
              aria-hidden="true"
            >
              Creating
            </span>
            <MenuLink
              to="/workspace"
              icon="workspace"
              title="My creations"
              detail="Everything you’ve made, drafts too"
            />
            {hasCredits ? (
              <MenuLink
                to="/credits"
                icon="credits"
                title="Credits"
                detail={
                  balance
                    ? `${creditsLabel(balance.credits)} · Buy more`
                    : "Buy and manage credits"
                }
              />
            ) : null}
          </div>
          <hr />
          <MenuLink
            to="/settings"
            icon="settings"
            title="Settings"
            detail="Name, email and picture"
          />
        </nav>
        {auth && (
          <>
            {error && <p role="alert">{error}</p>}
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await auth.signOut();
                } catch {
                  setError("Couldn’t sign out. Please try again.");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </details>
  );
}
