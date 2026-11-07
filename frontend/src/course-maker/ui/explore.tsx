import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { PublishedCourse, PublishedLesson } from "../application/creators";
import { Thumbnail } from "./components";
import {
  courseTopics,
  subtopicPath,
  topicPath,
  type CourseTopic,
} from "./course-catalog";
import { countLabel, courseMinutes } from "./explore-courses";
import { COURSE_CREATION_ENABLED } from "./feature-flags";
import { watchPath } from "./pages/CreatorProfilePage";
import { useCurrentInStrip } from "./use-current-in-strip";

/** What the catalogue is called while courses are hidden: everything is a lesson. */
export const exploreAllLabel = COURSE_CREATION_ENABLED
  ? "All courses"
  : "All lessons";

export function ExploreHero({
  topic,
  title,
  children,
}: {
  topic?: CourseTopic;
  title: string;
  children: ReactNode;
}) {
  return (
    <header className="explore-hero" data-tone={topic?.color ?? "lavender"}>
      <div className="explore-hero-copy">
        {topic ? (
          <nav className="explore-breadcrumb" aria-label="Breadcrumb">
            <Link to="/explore">{exploreAllLabel}</Link>
            <span aria-hidden="true">/</span>
            <span aria-current="page">{topic.title}</span>
          </nav>
        ) : (
          <p className="explore-eyebrow">Discover</p>
        )}
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      <span className="explore-hero-symbol" aria-hidden="true">
        {topic?.symbol ?? "✦"}
      </span>
    </header>
  );
}

/**
 * `count` returns how many items a tab holds (the whole catalogue when called
 * without a topic); leave it out while the catalogue is still loading.
 */
export function TopicTabs({
  count,
  current,
}: {
  count?: (topic?: CourseTopic) => number;
  current?: CourseTopic;
}) {
  const strip = useCurrentInStrip("page", current?.slug);
  return (
    <nav ref={strip} className="topic-filters explore-tabs" aria-label="Topics">
      <Link
        to="/explore"
        className={!current ? "selected" : ""}
        aria-current={!current ? "page" : undefined}
      >
        {exploreAllLabel}
        {count ? <span className="count">{count()}</span> : null}
      </Link>
      {courseTopics.map((topic) => (
        <Link
          key={topic.slug}
          to={topicPath(topic)}
          data-tone={topic.color}
          className={current?.slug === topic.slug ? "selected" : ""}
          aria-current={current?.slug === topic.slug ? "page" : undefined}
        >
          <span className="topic-dot" aria-hidden="true" />
          {topic.title}
          {count ? <span className="count">{count(topic)}</span> : null}
        </Link>
      ))}
    </nav>
  );
}

export function SubtopicTabs({
  topic,
  count,
  current,
}: {
  topic: CourseTopic;
  count?: (subtopic?: string) => number;
  current?: string;
}) {
  const strip = useCurrentInStrip("page", current);
  return (
    <nav
      ref={strip}
      className="topic-filters explore-subtabs"
      aria-label="Subtopics"
    >
      <Link
        to={topicPath(topic)}
        className={!current ? "selected" : ""}
        aria-current={!current ? "page" : undefined}
      >
        All {topic.title}
      </Link>
      {topic.subtopics.map((subtopic) => (
        <Link
          key={subtopic}
          to={subtopicPath(topic, subtopic)}
          className={current === subtopic ? "selected" : ""}
          aria-current={current === subtopic ? "page" : undefined}
        >
          {subtopic}
          {count ? <span className="count">{count(subtopic)}</span> : null}
        </Link>
      ))}
    </nav>
  );
}

/** A shelf previews a few items sideways on a phone; a full list stacks them. */
type GridLayout = "list" | "shelf";

export function LessonGrid({
  lessons,
  layout = "list",
}: {
  lessons: readonly PublishedLesson[];
  layout?: GridLayout;
}) {
  return (
    <div className="discovery-grid" data-layout={layout}>
      {lessons.map((lesson) => (
        <Link className="discovery-card" key={lesson.id} to={watchPath(lesson)}>
          <span className="discovery-card-art">
            <Thumbnail name={lesson.image} variant="lesson" />
            <span className="discovery-card-duration">
              {lesson.minutes} min
            </span>
          </span>
          <h3>{lesson.title}</h3>
          <span className="discovery-card-action">Watch lesson</span>
        </Link>
      ))}
    </div>
  );
}

export function ExploreCourseCard({ course }: { course: PublishedCourse }) {
  const first = course.lessons[0];
  const minutes = courseMinutes(course);
  return (
    <article className="discovery-card">
      <span className="discovery-card-art">
        <Thumbnail name={course.image} variant="course" />
        <span className="discovery-card-duration">
          {countLabel(course.lessons.length, "lesson")}
        </span>
      </span>
      <h3>{course.title}</h3>
      <p className="muted small">{course.description}</p>
      {minutes ? (
        <p className="discovery-card-meta">About {minutes} min of video</p>
      ) : null}
      {first ? (
        <Link className="discovery-card-action" to={watchPath(first)}>
          Start course →
        </Link>
      ) : null}
    </article>
  );
}

export function CourseGrid({
  courses,
  layout = "list",
}: {
  courses: readonly PublishedCourse[];
  layout?: GridLayout;
}) {
  return (
    <div className="discovery-grid" data-layout={layout}>
      {courses.map((course) => (
        <ExploreCourseCard key={course.id} course={course} />
      ))}
    </div>
  );
}

export function ExploreEmpty({
  title,
  children,
  to,
  action,
}: {
  title: string;
  children: ReactNode;
  to: string;
  action: string;
}) {
  return (
    <div className="discovery-empty">
      <h2>{title}</h2>
      <p className="muted">{children}</p>
      <Link to={to}>{action}</Link>
    </div>
  );
}
