import { COURSE_CREATION_ENABLED } from "../feature-flags";
import { useSearchParams } from "react-router-dom";
import { useCourses } from "../application-context";
import { useLessons } from "../lesson-context";
import {
  Books,
  CourseIcon,
  LessonIcon,
  LinkButton,
  QueryStatus,
  Thumbnail,
} from "../components";
import {
  isFinishedLesson,
  lessonWorkflowStatus,
  lessonWorkflowTone,
} from "../lesson-workflow";

type WorkspaceItem = Readonly<{
  id: string;
  title: string;
  description: string;
  kind: "Course" | "Lesson";
  status: "draft" | "finished";
  stage: string;
  tone: "working" | "ready" | "attention" | "draft";
  detail: string;
  image: string;
  to: string;
}>;

const statusFilters = [
  { value: "all", label: "All work" },
  { value: "draft", label: "Drafts" },
  { value: "finished", label: "Finished" },
] as const;
const typeFilters = [
  { value: "all", label: "All types" },
  { value: "course", label: "Courses" },
  { value: "lesson", label: "Lessons" },
] as const;
const sections = {
  draft: {
    title: "Drafts",
    description: "Work you’ve started. Continue any of it where you left off.",
  },
  finished: {
    title: "Finished",
    description: "Finished lesson videos, ready to watch or share.",
  },
} as const;

function plural(count: number, word: string) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function WorkspaceRow({ item }: { item: WorkspaceItem }) {
  const action = `${item.status === "draft" ? "Continue" : "Open"} ${item.kind.toLowerCase()}`;
  return (
    <li className="workspace-item">
      <div className="workspace-item-cover">
        <Thumbnail name={item.image} variant="course" />
      </div>
      <div className="workspace-item-copy">
        <span className="workspace-kind">
          {item.kind === "Course" ? <CourseIcon /> : <LessonIcon />}
          {item.kind}
          <span className="workspace-kind-detail">{item.detail}</span>
        </span>
        <h3>{item.title}</h3>
        {item.description ? (
          <p className="muted workspace-description">{item.description}</p>
        ) : null}
      </div>
      <span className="workflow-status" data-tone={item.tone}>
        {item.stage}
      </span>
      <LinkButton to={item.to} secondary>
        {action}
      </LinkButton>
    </li>
  );
}

export function WorkspacePage() {
  const courses = useCourses();
  const lessons = useLessons();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "all";
  const kind = params.get("type") ?? "all";
  const search = params.get("search") ?? "";
  const filter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value === "all" || !value) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };
  if (!courses.data || !lessons.data)
    return (
      <QueryStatus
        pending={courses.isPending || lessons.isPending}
        error={courses.error || lessons.error}
        retry={() => {
          void courses.refetch();
          void lessons.refetch();
        }}
      />
    );
  const items: WorkspaceItem[] = [
    ...(COURSE_CREATION_ENABLED ? courses.data : []).map(
      (course): WorkspaceItem => {
        const count = course.chapters.flatMap((c) => c.lessons).length;
        const stage =
          course.status === "ready"
            ? "Syllabus approved"
            : count
              ? "Review syllabus"
              : "Draft";
        return {
          id: course.id,
          title: course.title,
          description: course.description,
          kind: "Course",
          status: course.status === "draft" ? "draft" : "finished",
          stage,
          tone:
            course.status === "ready" ? "ready" : count ? "attention" : "draft",
          detail: count ? plural(count, "lesson") : "No syllabus yet",
          image: course.image,
          to: `/courses/${course.id}/${course.status === "draft" && !count ? "edit" : "syllabus"}`,
        };
      },
    ),
    ...lessons.data.map((lesson): WorkspaceItem => ({
      id: lesson.id,
      title: lesson.content.title,
      description: lesson.description,
      kind: "Lesson",
      status: isFinishedLesson(lesson) ? "finished" : "draft",
      stage: lessonWorkflowStatus(lesson),
      tone: lessonWorkflowTone(lesson),
      detail: `${lesson.content.minutes} min`,
      image: lesson.content.image,
      to: `/lessons/${lesson.id}${lesson.content.plan ? "" : "/edit"}`,
    })),
  ];
  const query = search.trim().toLowerCase();
  const visible = items.filter(
    (item) =>
      (status === "all" || item.status === status) &&
      (kind === "all" || item.kind.toLowerCase() === kind) &&
      `${item.title} ${item.description}`.toLowerCase().includes(query),
  );
  return (
    <div className="workspace-page">
      <div className="heading-row">
        <div className="page-heading">
          <h1>My creations</h1>
          <p className="muted">
            Everything you’re making, in one place. Continue a draft or open
            finished work.
          </p>
        </div>
        <div className="workspace-actions">
          <LinkButton to="/lessons/new">New lesson</LinkButton>
          {COURSE_CREATION_ENABLED ? (
            <LinkButton to="/courses/new">New course</LinkButton>
          ) : null}
        </div>
      </div>
      {items.length ? (
        <div className="workspace-toolbar">
          <div
            className="workspace-segments"
            role="group"
            aria-label="Filter by status"
          >
            {statusFilters.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                aria-pressed={status === value}
                onClick={() => filter("status", value)}
              >
                {label}
                <span className="workspace-count">
                  {
                    items.filter(
                      (item) => value === "all" || item.status === value,
                    ).length
                  }
                </span>
              </button>
            ))}
          </div>
          {COURSE_CREATION_ENABLED ? (
            <div
              className="workspace-segments workspace-segments-quiet"
              role="group"
              aria-label="Filter by type"
            >
              {typeFilters.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={kind === value}
                  onClick={() => filter("type", value)}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
          <div className="workspace-search">
            <label className="sr-only" htmlFor="workspace-search">
              Search workspace
            </label>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="6.5" />
              <path d="m16 16 4 4" />
            </svg>
            <input
              id="workspace-search"
              type="search"
              placeholder="Search by title or description"
              value={search}
              onChange={(e) => filter("search", e.target.value)}
            />
          </div>
        </div>
      ) : null}
      {(["draft", "finished"] as const).map((section) => {
        const entries = visible.filter((item) => item.status === section);
        if (!entries.length) return null;
        return (
          <section
            className="workspace-section"
            key={section}
            aria-labelledby={`workspace-${section}`}
          >
            <div className="home-section-heading">
              <div>
                <h2 id={`workspace-${section}`}>
                  {sections[section].title}{" "}
                  <span className="workspace-count">{entries.length}</span>
                </h2>
                <p className="muted">{sections[section].description}</p>
              </div>
            </div>
            <ul className="workspace-list">
              {entries.map((item) => (
                <WorkspaceRow key={item.id} item={item} />
              ))}
            </ul>
          </section>
        );
      })}
      {!visible.length &&
        (items.length ? (
          <div className="workspace-empty">
            <h2>No work matches these filters</h2>
            <p className="muted">
              {query
                ? `Nothing matches “${search.trim()}”. Try another word, status or type.`
                : status === "draft"
                  ? "You have no drafts here. Everything you’ve started is finished."
                  : status === "finished"
                    ? "Nothing is finished here yet. Your drafts are waiting."
                    : "Try another type."}
            </p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setParams({}, { replace: true })}
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="workspace-empty workspace-empty-first">
            <Books />
            <h2>Your next idea starts here</h2>
            <p className="muted">
              Start a lesson. Save it as a draft whenever you like, and it waits
              for you here.
            </p>
            <div className="workspace-actions">
              <LinkButton to="/lessons/new">Create a lesson</LinkButton>
              {COURSE_CREATION_ENABLED ? (
                <LinkButton to="/courses/new">Create a course</LinkButton>
              ) : null}
            </div>
          </div>
        ))}
    </div>
  );
}
