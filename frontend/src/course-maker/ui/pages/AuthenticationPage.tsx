import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type FormEvent,
  type ReactNode,
  type Ref,
} from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuthentication } from "../authentication";
import { accountPath, intentFor, safeReturnPath } from "../auth-routes";
import "../styles/authentication.css";

export { safeReturnPath };

type Mode =
  "login" | "signup" | "forgot-password" | "verify-email" | "reset-password";
type Purpose = "verify" | "reset";
type Outcome =
  | { kind: "sent"; purpose: Purpose; email: string; message: string }
  | { kind: "done"; message: string };
type FieldName = "first" | "last" | "email" | "password";

const MIN_PASSWORD = 15;
const RESEND_SECONDS = 30;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const icons = {
  mail: (
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="3" />
      <path d="m4.5 8.5 7.5 5 7.5-5" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.4 2.8 2.8 5.2-5.6" />
    </>
  ),
  alert: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5.2M12 16.4h.01" />
    </>
  ),
  eye: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="2.8" />
    </>
  ),
  eyeOff: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="2.8" />
      <path d="m4 4 16 16" />
    </>
  ),
};

function Icon({ name }: { name: keyof typeof icons }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="auth-icon">
      {icons[name]}
    </svg>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="auth-google-mark">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

function Field({
  label,
  name,
  type = "text",
  autoComplete,
  value,
  onChange,
  onBlur,
  error,
  hint,
  maxLength,
  inputRef,
  action,
  children,
}: {
  label: string;
  name: string;
  type?: string;
  autoComplete: string;
  value: string;
  onChange: (value: string) => void;
  onBlur: (event: FocusEvent<HTMLInputElement>) => void;
  error?: string;
  hint?: ReactNode;
  maxLength: number;
  inputRef?: Ref<HTMLInputElement>;
  /** Sits beside the label, e.g. “Forgot password?”. */
  action?: ReactNode;
  /** Replaces the plain input, e.g. to add a show/hide button. */
  children?: (props: {
    id: string;
    describedBy: string | undefined;
    invalid: boolean;
  }) => ReactNode;
}) {
  const id = useId();
  const hintId = id + "-hint";
  const errorId = id + "-error";
  const describedBy =
    [error ? errorId : "", hint ? hintId : ""].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className="auth-field" data-invalid={!!error || undefined}>
      <div className="auth-label-row">
        <label htmlFor={id}>{label}</label>
        {action}
      </div>
      {children ? (
        children({ id, describedBy, invalid: !!error })
      ) : (
        <input
          id={id}
          ref={inputRef}
          name={name}
          type={type}
          autoComplete={autoComplete}
          maxLength={maxLength}
          value={value}
          aria-invalid={!!error}
          aria-describedby={describedBy}
          spellCheck={type === "email" ? false : undefined}
          autoCapitalize={type === "email" ? "none" : undefined}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
        />
      )}
      {error ? (
        <p className="auth-field-error" id={errorId}>
          {error}
        </p>
      ) : null}
      {hint ? (
        <div className="auth-field-hint" id={hintId}>
          {hint}
        </div>
      ) : null}
    </div>
  );
}

function PasswordHint({ length }: { length: number }) {
  const met = length >= MIN_PASSWORD;
  return (
    <div className="auth-meter" data-met={met}>
      <span className="auth-meter-track" aria-hidden="true">
        <span
          className="auth-meter-fill"
          style={{ width: Math.min(100, (length / MIN_PASSWORD) * 100) + "%" }}
        />
      </span>
      <span className="auth-meter-text">
        {length === 0
          ? `Use ${MIN_PASSWORD} or more characters. Three or four random words work well.`
          : met
            ? "Long enough. Spaces and symbols are fine."
            : `${length} of ${MIN_PASSWORD} characters`}
      </span>
    </div>
  );
}

const copy: Record<
  Mode,
  { title: string; action: string; busy: string; lede: string }
> = {
  login: {
    title: "Welcome back",
    action: "Sign in",
    busy: "Signing in…",
    lede: "Pick up where you left off.",
  },
  signup: {
    title: "Create your account",
    action: "Create account",
    busy: "Creating account…",
    lede: "Turn any idea into a narrated, animated lesson.",
  },
  "forgot-password": {
    title: "Reset your password",
    action: "Send reset link",
    busy: "Sending…",
    lede: "Enter your email and we’ll send you a link to choose a new password.",
  },
  "verify-email": {
    title: "Resend verification email",
    action: "Send verification link",
    busy: "Sending…",
    lede: "Enter your email and we’ll send a fresh link to confirm your address.",
  },
  "reset-password": {
    title: "Choose a new password",
    action: "Update password",
    busy: "Updating…",
    lede: "Pick something new. You’ll sign in with it right after.",
  },
};

export function AuthenticationPage({ mode }: { mode: Mode }) {
  const auth = useAuthentication();
  const navigate = useNavigate();
  const location = useLocation();
  const search = new URLSearchParams(location.search);
  const returnTo = safeReturnPath(search.get("returnTo"));
  const intent = intentFor(returnTo);
  const carried = (location.state as { email?: string } | null)?.email;
  const [email, setEmail] = useState(carried ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  // Fragments are not sent to servers or access logs. Remove the secret from history on submit.
  const [token] = useState(
    () => new URLSearchParams(location.hash.slice(1)).get("token") ?? "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [touched, setTouched] = useState<Set<FieldName>>(new Set());
  const [submitted, setSubmitted] = useState(false);
  const refs = {
    first: useRef<HTMLInputElement>(null),
    last: useRef<HTMLInputElement>(null),
    email: useRef<HTMLInputElement>(null),
    password: useRef<HTMLInputElement>(null),
  };

  const resendOnly = mode === "verify-email" && !!token;
  const asksForEmail =
    ["login", "signup", "forgot-password"].includes(mode) ||
    (mode === "verify-email" && !token);
  const asksForPassword = ["login", "signup", "reset-password"].includes(mode);
  const choosingPassword = mode === "signup" || mode === "reset-password";
  const missingResetLink = mode === "reset-password" && !token;
  const text = copy[mode];

  useEffect(() => {
    // Phones raise a keyboard over the page when a field takes focus on load.
    if (window.matchMedia?.("(pointer: fine)").matches)
      (refs.first.current ?? refs.email.current)?.focus();
  }, []);

  // The form is replaced by a confirmation; keep keyboard and screen reader
  // users in the page by moving them to its heading.
  const outcomeKind = outcome?.kind;
  useEffect(() => {
    if (outcomeKind) document.getElementById("auth-title")?.focus();
  }, [outcomeKind]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  // Someone who is already signed in has nothing to do here.
  if (
    auth?.session?.user &&
    ["login", "signup", "forgot-password"].includes(mode)
  )
    return <Navigate to={returnTo} replace />;

  const problems: Partial<Record<FieldName, string>> = {};
  if (mode === "signup") {
    if (!firstName.trim()) problems.first = "Enter your first name.";
    if (!lastName.trim()) problems.last = "Enter your last name.";
  }
  if (asksForEmail) {
    if (!email.trim()) problems.email = "Enter your email address.";
    else if (!EMAIL_PATTERN.test(email.trim()))
      problems.email = "Enter a valid email, like name@example.com.";
  }
  if (asksForPassword) {
    if (!password)
      problems.password =
        mode === "login" ? "Enter your password." : "Choose a password.";
    else if (choosingPassword && password.length < MIN_PASSWORD)
      problems.password = `Use at least ${MIN_PASSWORD} characters.`;
  }
  const visible = (field: FieldName) =>
    submitted || touched.has(field) ? problems[field] : undefined;
  // Only nag when someone moves on to another field. A message that appears as
  // the pointer heads for the button would shift it away and swallow the click;
  // submitting checks every field anyway.
  const leave = (field: FieldName) => (event: FocusEvent<HTMLInputElement>) => {
    if (event.relatedTarget instanceof HTMLInputElement)
      setTouched((current) => new Set(current).add(field));
  };

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!auth || busy) return;
    setSubmitted(true);
    const first = (["first", "last", "email", "password"] as const).find(
      (field) => problems[field],
    );
    if (first) {
      refs[first].current?.focus();
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (token) navigate(location.pathname, { replace: true });
      const address = email.trim();
      if (mode === "login") {
        auth.accept(await auth.client.signIn(address, password));
        setPassword("");
        navigate(returnTo, { replace: true });
      } else if (mode === "signup") {
        const message = await auth.client.signUp({
          email: address,
          password,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
        });
        setPassword("");
        setOutcome({
          kind: "sent",
          purpose: "verify",
          email: address,
          message,
        });
        setCooldown(RESEND_SECONDS);
      } else if (mode === "forgot-password" || asksForEmail) {
        const purpose = mode === "forgot-password" ? "reset" : "verify";
        const message = await auth.client.requestEmail(address, purpose);
        setOutcome({ kind: "sent", purpose, email: address, message });
        setCooldown(RESEND_SECONDS);
      } else {
        const message = await auth.client.completeEmail(
          token,
          mode === "reset-password" ? "reset" : "verify",
          password,
        );
        setPassword("");
        setOutcome({ kind: "done", message });
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function resend(sent: Extract<Outcome, { kind: "sent" }>) {
    if (!auth || busy || cooldown > 0) return;
    setBusy(true);
    setError("");
    try {
      const message = await auth.client.requestEmail(sent.email, sent.purpose);
      setOutcome({ ...sent, message });
      setCooldown(RESEND_SECONDS);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function google() {
    if (!auth) return;
    setBusy(true);
    setError("");
    try {
      const target = await auth.client.beginGoogle();
      // The redirect is controlled by the server; constrain it again at the browser boundary.
      if (new URL(target).origin !== "https://accounts.google.com")
        throw new Error("Invalid sign-in destination");
      // Full navigation is necessary for the provider's OAuth session.
      auth.navigateProvider(target);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Google sign-in failed.",
      );
      setBusy(false);
    }
  }

  const oauthError = search.get("error");
  const oauthMessage = oauthError
    ? oauthError === "account_exists"
      ? "An account already uses this email. Sign in with your original method."
      : "Google sign-in wasn’t completed. Please try again."
    : "";
  const keep = (page: "/login" | "/signup") => accountPath(page, returnTo);
  const lede =
    mode === "login" && intent
      ? `Sign in to ${intent}.`
      : mode === "signup" && intent
        ? `Create an account to ${intent}.`
        : text.lede;
  const showGoogle =
    ["login", "signup"].includes(mode) && !!auth?.session?.google_enabled;
  const linkProblem =
    !!error &&
    (mode === "verify-email" || mode === "reset-password") &&
    !!token;

  let body: ReactNode;
  if (!auth) {
    body = (
      <>
        <header className="auth-header">
          <h1 id="auth-title" tabIndex={-1}>
            {text.title}
          </h1>
        </header>
        <p className="auth-lede">
          Account sign-in is unavailable in demo mode.
        </p>
      </>
    );
  } else if (outcome?.kind === "sent") {
    const lifetime = outcome.purpose === "reset" ? "30 minutes" : "24 hours";
    body = (
      <div className="auth-result">
        <span className="auth-result-icon" data-tone="lavender">
          <Icon name="mail" />
        </span>
        <h1 id="auth-title" tabIndex={-1}>
          Check your email
        </h1>
        <p role="status" className="auth-lede">
          {outcome.message}
        </p>
        <p className="auth-fine">
          The link works for {lifetime}. If it isn’t in your inbox, check your
          spam folder.
        </p>
        {error ? (
          <p role="alert" className="auth-alert">
            <Icon name="alert" />
            <span>{error}</span>
          </p>
        ) : null}
        <button
          type="button"
          className="btn btn-secondary auth-submit"
          disabled={busy || cooldown > 0}
          onClick={() => void resend(outcome)}
        >
          {cooldown > 0 ? `Resend email in ${cooldown}s` : "Resend email"}
        </button>
        <p className="auth-links">
          <button
            type="button"
            className="auth-text-button"
            onClick={() => {
              setOutcome(null);
              setError("");
            }}
          >
            Use a different email
          </button>
          <Link to="/login">Back to sign in</Link>
        </p>
      </div>
    );
  } else if (outcome?.kind === "done") {
    body = (
      <div className="auth-result">
        <span className="auth-result-icon" data-tone="sage">
          <Icon name="check" />
        </span>
        <h1 id="auth-title" tabIndex={-1}>
          {mode === "reset-password" ? "Password updated" : "Email verified"}
        </h1>
        <p role="status" className="auth-lede">
          {mode === "reset-password"
            ? "Sign in with your new password. Your other devices were signed out."
            : "Your account is ready. Sign in to start creating."}
        </p>
        <Link className="btn btn-primary auth-submit" to="/login">
          Continue to sign in
        </Link>
      </div>
    );
  } else {
    body = (
      <>
        <header className="auth-header">
          <h1 id="auth-title" tabIndex={-1}>
            {resendOnly ? "Confirm your email" : text.title}
          </h1>
          <p className="auth-lede">
            {resendOnly
              ? "One more step to finish setting up your account."
              : lede}
          </p>
        </header>
        {oauthMessage ? (
          <p role="alert" className="auth-alert">
            <Icon name="alert" />
            <span>{oauthMessage}</span>
          </p>
        ) : null}
        {showGoogle ? (
          <>
            <button
              type="button"
              className="btn btn-secondary auth-google"
              disabled={busy || auth.loading}
              onClick={() => void google()}
            >
              <GoogleMark />
              Continue with Google
            </button>
            <p className="auth-divider">
              <span>or use your email</span>
            </p>
          </>
        ) : null}
        {missingResetLink ? (
          <div className="auth-notice">
            <p>
              This page needs the link from your password reset email. Open that
              link, or ask for a new one.
            </p>
            <Link className="btn btn-primary auth-submit" to="/forgot-password">
              Send a new reset link
            </Link>
          </div>
        ) : (
          <form onSubmit={(event) => void submit(event)} noValidate>
            {error ? (
              <p role="alert" className="auth-alert">
                <Icon name="alert" />
                <span>
                  {error}
                  {mode === "login" ? (
                    <>
                      {" "}
                      <Link
                        to="/forgot-password"
                        state={{ email: email.trim() }}
                      >
                        Reset your password
                      </Link>{" "}
                      or{" "}
                      <Link to="/verify-email" state={{ email: email.trim() }}>
                        resend the verification email
                      </Link>
                      .
                    </>
                  ) : null}
                  {linkProblem ? (
                    <>
                      {" "}
                      <Link
                        to={
                          mode === "reset-password"
                            ? "/forgot-password"
                            : "/verify-email"
                        }
                      >
                        Request a new link
                      </Link>
                      .
                    </>
                  ) : null}
                </span>
              </p>
            ) : null}
            {mode === "signup" ? (
              <div className="auth-names">
                <Field
                  label="First name"
                  name="given-name"
                  autoComplete="given-name"
                  maxLength={100}
                  value={firstName}
                  onChange={setFirstName}
                  onBlur={leave("first")}
                  error={visible("first")}
                  inputRef={refs.first}
                />
                <Field
                  label="Last name"
                  name="family-name"
                  autoComplete="family-name"
                  maxLength={100}
                  value={lastName}
                  onChange={setLastName}
                  onBlur={leave("last")}
                  error={visible("last")}
                  inputRef={refs.last}
                />
              </div>
            ) : null}
            {asksForEmail ? (
              <Field
                label="Email"
                name="email"
                type="email"
                autoComplete="email"
                maxLength={320}
                value={email}
                onChange={setEmail}
                onBlur={leave("email")}
                error={visible("email")}
                inputRef={refs.email}
              />
            ) : null}
            {asksForPassword ? (
              <Field
                label={mode === "reset-password" ? "New password" : "Password"}
                name="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                maxLength={128}
                value={password}
                onChange={setPassword}
                onBlur={leave("password")}
                error={visible("password")}
                hint={
                  choosingPassword ? (
                    <PasswordHint length={password.length} />
                  ) : undefined
                }
                action={
                  mode === "login" ? (
                    <Link
                      className="auth-forgot"
                      to="/forgot-password"
                      state={{ email: email.trim() }}
                    >
                      Forgot password?
                    </Link>
                  ) : undefined
                }
              >
                {({ id, describedBy, invalid }) => (
                  <div className="auth-password">
                    <input
                      id={id}
                      ref={refs.password}
                      name="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete={
                        mode === "login" ? "current-password" : "new-password"
                      }
                      maxLength={128}
                      value={password}
                      aria-invalid={invalid}
                      aria-describedby={describedBy}
                      onChange={(event) => setPassword(event.target.value)}
                      onBlur={leave("password")}
                    />
                    <button
                      type="button"
                      className="auth-reveal"
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                      aria-pressed={showPassword}
                      onClick={() => setShowPassword((shown) => !shown)}
                    >
                      <Icon name={showPassword ? "eyeOff" : "eye"} />
                    </button>
                  </div>
                )}
              </Field>
            ) : null}
            <button
              type="submit"
              className="btn btn-primary auth-submit"
              disabled={busy || auth.loading}
              aria-busy={busy}
            >
              {busy ? (
                <>
                  <span className="auth-spinner" aria-hidden="true" />
                  {text.busy}
                </>
              ) : resendOnly ? (
                "Verify your email"
              ) : (
                text.action
              )}
            </button>
          </form>
        )}
        <nav className="auth-links" aria-label="Account help">
          {mode === "login" ? (
            <>
              <p>
                New to Course Maker?{" "}
                <Link to={keep("/signup")} state={{ email: email.trim() }}>
                  Create an account
                </Link>
              </p>
              <p>
                Didn’t get a verification email?{" "}
                <Link to="/verify-email" state={{ email: email.trim() }}>
                  Resend it
                </Link>
              </p>
            </>
          ) : mode === "signup" ? (
            <p>
              Already have an account?{" "}
              <Link to={keep("/login")} state={{ email: email.trim() }}>
                Sign in
              </Link>
            </p>
          ) : (
            <p>
              <Link to="/login">Back to sign in</Link>
            </p>
          )}
        </nav>
      </>
    );
  }

  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <p className="auth-aside-title">
          Describe an idea. Watch it become a lesson.
        </p>
        <ol className="auth-steps">
          <li>
            <b>1</b>
            <span>
              Say what you want to learn
              <small>A title and a few words about it</small>
            </span>
          </li>
          <li>
            <b>2</b>
            <span>
              Review the outline
              <small>Edit it, or ask the guide for changes</small>
            </span>
          </li>
          <li>
            <b>3</b>
            <span>
              Get a narrated, animated video
              <small>Ready in a few minutes</small>
            </span>
          </li>
        </ol>
        <img
          className="auth-aside-art"
          src="/course-maker/learning-books.svg"
          alt=""
          width={480}
          height={320}
        />
      </aside>
      <section className="auth-card" aria-labelledby="auth-title">
        {body}
        {auth && !outcome ? (
          <p className="auth-browse">
            Just looking around? <Link to="/explore">Browse lessons</Link>, no
            account needed.
          </p>
        ) : null}
      </section>
    </div>
  );
}
