import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { PublishedCourse, PublishedLesson } from "../application/creators";
import { Progress, Thumbnail } from "./components";
import { courseTopics, topicPath } from "./course-catalog";
import { countLabel } from "./explore-courses";
import type { HomeItem } from "./home-feed";
import { watchPath } from "./pages/CreatorProfilePage";

export function HomeFeature({
  eyebrow,
  title,
  detail,
  image,
  variant,
  to,
  action,
  progress,
  status,
  priority = false,
}: Readonly<{
  eyebrow: string;
  title: string;
  detail: string;
  image: string;
  variant: "course" | "lesson";
  to: string;
  action: string;
  progress?: HomeItem["progress"];
  status?: HomeItem["status"];
  /** On a phone, picking up unfinished work comes before anything else. */
  priority?: boolean;
}>) {
  const titleId = useId();
  return (
    <section
      className="home-feature"
      data-priority={priority || undefined}
      aria-labelledby={titleId}
    >
      <div className="home-feature-copy">
        <p className="home-feature-eyebrow">{eyebrow}</p>
        <h2 id={titleId}>{title}</h2>
        <p className="home-feature-detail">{detail}</p>
        {status ? (
          <span className="workflow-status" data-tone={status.tone}>
            {status.label}
          </span>
        ) : null}
        {progress ? (
          <div className="home-feature-progress">
            <Progress completed={progress.completed} total={progress.total} />
            <span>
              {progress.completed} of {progress.total} lessons complete
            </span>
          </div>
        ) : null}
        <Link className="btn home-feature-action" to={to}>
          {action}
        </Link>
      </div>
      <div className="home-feature-art">
        <Thumbnail name={image} variant={variant} />
      </div>
    </section>
  );
}

export function HomeFeatureSkeleton() {
  return (
    <div
      className="home-feature home-skeleton"
      data-priority
      aria-hidden="true"
    />
  );
}

function RailArrow({
  direction,
  onClick,
}: Readonly<{ direction: "back" | "forward"; onClick(): void }>) {
  return (
    <button
      type="button"
      className="home-rail-arrow"
      data-direction={direction}
      tabIndex={-1}
      aria-hidden="true"
      // A hidden control must not take focus when clicked.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    />
  );
}

export function HomeRail({
  title,
  link,
  size = "regular",
  count,
  children,
}: Readonly<{
  title: string;
  link?: Readonly<{ to: string; label: string }>;
  size?: "regular" | "wide";
  count: number;
  children: ReactNode;
}>) {
  const titleId = useId();
  const track = useRef<HTMLUListElement>(null);
  const [edges, setEdges] = useState({ back: false, forward: false });
  useEffect(() => {
    const element = track.current;
    if (!element) return;
    const update = () =>
      setEdges({
        back: element.scrollLeft > 1,
        forward:
          element.scrollLeft + element.clientWidth < element.scrollWidth - 1,
      });
    update();
    element.addEventListener("scroll", update, { passive: true });
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(element);
    return () => {
      element.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [count]);
  const scroll = (direction: 1 | -1) => {
    const element = track.current;
    if (!element) return;
    const still = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    element.scrollBy({
      left: direction * element.clientWidth * 0.8,
      behavior: still ? "auto" : "smooth",
    });
  };
  return (
    <section className="home-rail" data-size={size} aria-labelledby={titleId}>
      <div className="home-rail-heading">
        <h2 id={titleId}>{title}</h2>
        {link ? <Link to={link.to}>{link.label}</Link> : null}
      </div>
      <div className="home-rail-body">
        <ul className="home-rail-track" ref={track}>
          {children}
        </ul>
        {/* Pointer shortcuts only: keyboard focus already scrolls cards into view. */}
        {edges.back ? (
          <RailArrow direction="back" onClick={() => scroll(-1)} />
        ) : null}
        {edges.forward ? (
          <RailArrow direction="forward" onClick={() => scroll(1)} />
        ) : null}
      </div>
    </section>
  );
}

export function WorkCard({ item }: { item: HomeItem }) {
  return (
    <li className="home-card">
      <Link to={item.to}>
        <span className="home-card-art">
          <Thumbnail name={item.image} variant={item.variant} />
          {item.status ? (
            <span className="workflow-status" data-tone={item.status.tone}>
              {item.status.label}
            </span>
          ) : null}
          {item.progress ? (
            <Progress
              completed={item.progress.completed}
              total={item.progress.total}
              label={item.title + " progress"}
            />
          ) : null}
        </span>
        <strong>{item.title}</strong>
        <span className="home-card-detail">{item.detail}</span>
      </Link>
    </li>
  );
}

export function PublicLessonCard({ lesson }: { lesson: PublishedLesson }) {
  return (
    <li className="home-card">
      <Link to={watchPath(lesson)}>
        <span className="home-card-art">
          <Thumbnail name={lesson.image} variant="lesson" />
          <span className="discovery-card-duration">{lesson.minutes} min</span>
        </span>
        <strong>{lesson.title}</strong>
      </Link>
    </li>
  );
}

export function PublicCourseCard({ course }: { course: PublishedCourse }) {
  const first = course.lessons[0];
  if (!first) return null;
  return (
    <li className="home-card">
      <Link to={watchPath(first)}>
        <span className="home-card-art">
          <Thumbnail name={course.image} variant="course" />
          <span className="discovery-card-duration">
            {countLabel(course.lessons.length, "lesson")}
          </span>
        </span>
        <strong>{course.title}</strong>
        <span className="home-card-detail">{course.description}</span>
      </Link>
    </li>
  );
}

export function SkeletonCards() {
  return (
    <>
      {[0, 1, 2, 3, 4].map((key) => (
        <li className="home-card" key={key} aria-hidden="true">
          <span className="home-card-art home-skeleton" />
        </li>
      ))}
    </>
  );
}

export function BrowseTopics() {
  const titleId = useId();
  return (
    <section className="home-topics" aria-labelledby={titleId}>
      <div className="home-rail-heading">
        <h2 id={titleId}>Browse by topic</h2>
        <Link to="/explore">See all courses</Link>
      </div>
      <div className="home-topics-grid">
        {courseTopics.map((topic) => (
          <Link key={topic.slug} to={topicPath(topic)} data-tone={topic.color}>
            <span className="home-topic-symbol" aria-hidden="true">
              {topic.symbol}
            </span>
            <strong>{topic.title}</strong>
            <span className="home-topic-blurb">{topic.blurb}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
