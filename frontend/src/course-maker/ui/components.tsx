import { COURSE_CREATION_ENABLED } from "./feature-flags";
import {
  Link,
  NavLink,
  useInRouterContext,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { INSUFFICIENT_CREDITS_STATUS } from "../application/credits";
import { Activity, useEffect, useRef, type ReactNode } from "react";
import type { CourseResponse } from "../application/dto";
import { CourseSearch, ExploreNavigation } from "./DiscoveryNavigation";
import { AccountMenu } from "./AccountMenu";
import { CreditBalanceChip } from "./CreditBalance";
import { useApplication } from "./application-context";
import { countLabel } from "./explore-courses";
import { SheetClose } from "./SheetClose";
import { useSignedIn } from "./authentication";

const asset = (name: string) => "/course-maker/" + name + ".svg";
const artwork: Record<string, string> = {
  python: "lesson-imgThumbnailPython",
  story: "home-imgThumbnailStory",
  ...Object.fromEntries(
    [
      "variables",
      "strings",
      "decisions",
      "loops",
      "lists",
      "lists1",
      "dict",
      "read",
      "write",
      "functions",
      "functions1",
      "parameters",
      "errors",
      "modules",
      "build",
      "plan",
      "build1",
      "test",
      "personal",
    ].map((key) => [
      key,
      "lesson-imgThumbnail" + key[0].toUpperCase() + key.slice(1),
    ]),
  ),
};
export function Thumbnail({
  name,
  variant = "lesson",
}: {
  name: string;
  variant?: "course" | "chapter" | "lesson";
}) {
  const source =
    variant === "course" && name === "python"
      ? "home-imgThumbnailPython"
      : (artwork[name] ?? artwork.story);
  return (
    <span className={"thumbnail thumbnail-" + variant}>
      <img
        src={
          /^(data:image\/svg\+xml;base64,[A-Za-z0-9+/]+=*|https?:\/\/[^\s]+)$/.test(
            name,
          )
            ? name
            : ["inertia", "history", "math"].includes(name)
              ? `/course-maker/thumbnails/${name}.svg`
              : asset(source)
        }
        alt=""
        onError={(event) => {
          const fallback = asset(artwork.story);
          if (event.currentTarget.getAttribute("src") !== fallback)
            event.currentTarget.src = fallback;
        }}
      />
    </span>
  );
}
export function LessonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="3" />
      <path d="M10.5 9.5v5l4-2.5z" fill="currentColor" stroke="none" />
    </svg>
  );
}
export function CourseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="4" width="16" height="4.5" rx="1.5" />
      <rect x="4" y="10" width="16" height="4.5" rx="1.5" />
      <rect x="4" y="16" width="10" height="4" rx="1.5" />
    </svg>
  );
}
export function Spark() {
  return <img className="spark" src={asset("setup-imgFrame1")} alt="" />;
}
export function Books() {
  return (
    <img
      className="books"
      src="/course-maker/learning-books.svg"
      width={480}
      height={320}
      alt=""
    />
  );
}
function CreateMenu() {
  const disclosure = useRef<HTMLDetailsElement>(null);
  const location = useLocation();
  const navigate = useNavigate();
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
  return (
    <details
      className="create-menu"
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
      <summary
        className="btn btn-primary"
        tabIndex={0}
        data-current={location.pathname === "/lessons/new" || undefined}
        onClick={(event) => {
          // A menu with one choice is a wasted tap on a phone.
          if (
            !COURSE_CREATION_ENABLED &&
            window.matchMedia?.("(max-width: 760px)").matches
          ) {
            event.preventDefault();
            navigate("/lessons/new");
          }
        }}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        Create
        <span className="chevron" aria-hidden="true" />
      </summary>
      <nav
        className="create-panel"
        aria-label="Create something new"
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a") && disclosure.current)
            disclosure.current.open = false;
        }}
      >
        <div className="sheet-heading">
          <strong>Create something new</strong>
          <SheetClose label="Close create menu" />
        </div>
        <Link className="create-option" to="/lessons/new">
          <LessonIcon />
          <span>
            <strong>New lesson</strong>
            <span>Bring one topic to life</span>
          </span>
          <span className="create-arrow" aria-hidden="true">
            ↗
          </span>
        </Link>
        {COURSE_CREATION_ENABLED ? (
          <Link className="create-option" to="/courses/new">
            <CourseIcon />
            <span>
              <strong>New course</strong>
              <span>Build a complete learning journey</span>
            </span>
            <span className="create-arrow" aria-hidden="true">
              ↗
            </span>
          </Link>
        ) : null}
      </nav>
    </details>
  );
}
export function Layout({ children }: { children: ReactNode }) {
  const live = !!useApplication().generateSyllabus;
  const signedIn = useSignedIn();
  return (
    <div className="cm-app">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <header className="app-header">
        <div className="nav-inner">
          <Link className="brand" to="/" aria-label="Course Maker home">
            <img
              src="/course-maker/brand-mark.svg"
              width={32}
              height={32}
              alt=""
            />
            course maker
          </Link>
          <nav className="main-nav" aria-label="Main navigation">
            <NavLink to="/" end>
              <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 6.5C4 5.7 4.7 5 5.5 5H10c1.1 0 2 .9 2 2v12c0-.8-.7-1.5-1.5-1.5h-5c-.8 0-1.5-.7-1.5-1.5z" />
                <path d="M20 6.5c0-.8-.7-1.5-1.5-1.5H14c-1.1 0-2 .9-2 2v12c0-.8.7-1.5 1.5-1.5h5c.8 0 1.5-.7 1.5-1.5z" />
              </svg>
              {signedIn ? "My learning" : "Home"}
            </NavLink>
            <ExploreNavigation />
          </nav>
          <CourseSearch />
          <CreateMenu />
          <div className="profile">
            <CreditBalanceChip />
            <AccountMenu />
          </div>
        </div>
      </header>
      <main id="content" className="workspace">
        {children}
      </main>
      <footer className="app-footer">
        A little curiosity, every day.{" "}
        <span>
          {!signedIn
            ? "Anyone can watch. Sign in when you’re ready to create."
            : live
              ? "Your lessons and conversations are saved."
              : "Demo data saved in this browser · AI and video generation aren’t connected yet."}
        </span>
      </footer>
    </div>
  );
}
export function LinkButton({
  to,
  children,
  secondary = false,
}: {
  to: string;
  children: ReactNode;
  secondary?: boolean;
}) {
  return (
    <Link
      className={"btn btn-" + (secondary ? "secondary" : "primary")}
      to={to}
    >
      {children}
    </Link>
  );
}
export function PageHeading({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      {children ? <p className="muted">{children}</p> : null}
    </div>
  );
}
export function Progress({
  completed,
  total,
  label = "Lesson progress",
}: {
  completed: number;
  total: number;
  label?: string;
}) {
  return (
    <progress aria-label={label} value={completed} max={Math.max(1, total)} />
  );
}
export function durationLabel(course: CourseResponse) {
  const d = course.duration;
  return d.mode === "total"
    ? d.hours + "-hour lesson"
    : countLabel(d.weeks, "week") +
        " · " +
        countLabel(d.hoursPerWeek, "hour") +
        " / week";
}
export function Summary({ course }: { course: CourseResponse }) {
  const lessons = course.chapters.flatMap((c) => c.lessons);
  return (
    <p className="muted small">
      {durationLabel(course)} · {lessons.length} lessons
    </p>
  );
}
export function ErrorNotice({ error }: { error: unknown }) {
  const routed = useInRouterContext();
  if (!error) return null;
  const outOfCredits =
    typeof error === "object" &&
    "status" in error &&
    error.status === INSUFFICIENT_CREDITS_STATUS;
  return (
    <p role="alert" className="error-notice">
      {error instanceof Error
        ? error.message
        : "Something went wrong. Please try again."}
      {outOfCredits && routed ? (
        <Link className="error-notice-action" to="/credits">
          Buy credits
        </Link>
      ) : null}
    </p>
  );
}
export function QueryStatus({
  pending,
  error,
  retry,
}: {
  pending: boolean;
  error: unknown;
  retry: () => void;
}) {
  return (
    <div className="status-panel" role="status">
      {pending ? (
        <>
          <Spark />
          <h1>Getting your learning space ready…</h1>
        </>
      ) : (
        <>
          <h1>We couldn’t open this page.</h1>
          <ErrorNotice error={error} />
          <button className="btn btn-primary" onClick={retry}>
            Try again
          </button>
          <Link to="/">Back to my learning</Link>
        </>
      )}
    </div>
  );
}

export function QueryWorkspace({
  error,
  retry,
  children,
}: {
  error: unknown;
  retry: () => void;
  children: ReactNode;
}) {
  return (
    <>
      {error ? (
        <QueryStatus pending={false} error={error} retry={retry} />
      ) : null}
      <Activity mode={error ? "hidden" : "visible"}>{children}</Activity>
    </>
  );
}
