import { COURSE_CREATION_ENABLED } from "../feature-flags";
import { useEffect, useRef, type ReactNode } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import type {
  PublishedCourse,
  PublishedLesson,
} from "../../application/creators";
import { QueryStatus, Thumbnail } from "../components";
import { useContentSearch } from "../use-content-search";
import { courseTopics, topicPath, type CourseTopic } from "../course-catalog";
import {
  countLabel,
  coursesInTopic,
  coursesWithoutTopic,
  lessonsInTopic,
  lessonsWithoutTopic,
} from "../explore-courses";
import {
  CourseGrid,
  ExploreEmpty,
  ExploreHero,
  LessonGrid,
  TopicTabs,
  exploreAllLabel,
} from "../explore";
import { LessonDiscovery } from "../LessonDiscovery";
import { useDiscovery } from "../use-discovery";

const shelfSize = 3;
const newestSize = 3;

export function ExplorePage() {
  const [params] = useSearchParams();
  const search = (params.get("q") ?? "").trim();
  const discovery = useDiscovery(undefined, !search);
  const courses =
    discovery.data?.courses ??
    (discovery.isFetching || discovery.error ? undefined : []);
  const lessons =
    discovery.data?.lessons ??
    (discovery.isFetching || discovery.error ? undefined : []);
  const status =
    discovery.error || (discovery.isFetching && !discovery.data) ? (
      <QueryStatus
        pending={discovery.isFetching}
        error={discovery.error}
        retry={() => void discovery.refetch()}
      />
    ) : null;
  if (!COURSE_CREATION_ENABLED)
    return (
      <div className="explore">
        <ExploreHero title={search ? "Search results" : exploreAllLabel}>
          {search
            ? `Lessons that match “${search}”.`
            : "Browse the lessons creators have published, one topic at a time."}
        </ExploreHero>
        <TopicTabs
          count={
            !search && lessons
              ? (topic) =>
                  topic ? lessonsInTopic(lessons, topic).length : lessons.length
              : undefined
          }
        />
        {search ? (
          <SearchResults search={search} />
        ) : (
          <>
            {status}
            {lessons?.length ? (
              <>
                <LessonDiscovery limit={newestSize} />
                <LessonTopicShelves lessons={lessons} />
              </>
            ) : lessons ? (
              <ExploreEmpty
                title="No public lessons yet"
                to="/lessons/new"
                action="Create a lesson →"
              >
                Lessons that creators publish show up here.
              </ExploreEmpty>
            ) : null}
          </>
        )}
      </div>
    );
  return (
    <div className="explore">
      <ExploreHero title={search ? "Search results" : "All courses"}>
        {search
          ? `Courses and lessons that match “${search}”.`
          : "Browse what creators have published, one topic at a time."}
      </ExploreHero>
      <TopicTabs
        count={
          !search && courses
            ? (topic) =>
                topic ? coursesInTopic(courses, topic).length : courses.length
            : undefined
        }
      />
      {status}
      {search ? (
        <SearchResults search={search} />
      ) : courses ? (
        <>
          {courses.length ? (
            <TopicShelves courses={courses} />
          ) : (
            <ExploreEmpty
              title="No public lessons yet"
              to="/lessons/new"
              action="Create a lesson →"
            >
              Lessons that creators publish show up here.
            </ExploreEmpty>
          )}
          <LessonDiscovery />
        </>
      ) : null}
    </div>
  );
}

function TopicShelf({
  id,
  topic,
  title,
  count,
  children,
}: {
  id: string;
  topic?: CourseTopic;
  title: string;
  count: string;
  children: ReactNode;
}) {
  return (
    <section className="explore-shelf" aria-labelledby={`shelf-${id}`}>
      <div className="explore-shelf-heading">
        <span
          className="explore-shelf-badge"
          data-tone={topic?.color ?? "sage"}
        >
          {topic?.symbol ?? "···"}
        </span>
        <div>
          <h2 id={`shelf-${id}`}>{title}</h2>
          <p className="muted">{count}</p>
        </div>
        {topic ? (
          <Link
            className="explore-see-all"
            to={topicPath(topic)}
            aria-label={`See all ${topic.title}`}
          >
            See all
            <span className="explore-see-all-topic"> {topic.title}</span> →
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function LessonTopicShelves({
  lessons,
}: {
  lessons: readonly PublishedLesson[];
}) {
  const other = lessonsWithoutTopic(lessons);
  return (
    <>
      {courseTopics.map((topic) => {
        const matches = lessonsInTopic(lessons, topic);
        if (!matches.length) return null;
        return (
          <TopicShelf
            key={topic.slug}
            id={topic.slug}
            topic={topic}
            title={topic.title}
            count={countLabel(matches.length, "lesson")}
          >
            <LessonGrid lessons={matches.slice(0, shelfSize)} layout="shelf" />
          </TopicShelf>
        );
      })}
      {other.length ? (
        <TopicShelf
          id="more"
          title="More lessons"
          count={countLabel(other.length, "lesson")}
        >
          <LessonGrid lessons={other} />
        </TopicShelf>
      ) : null}
    </>
  );
}

function TopicShelves({ courses }: { courses: readonly PublishedCourse[] }) {
  const other = coursesWithoutTopic(courses);
  return (
    <>
      {courseTopics.map((topic) => {
        const matches = coursesInTopic(courses, topic);
        if (!matches.length) return null;
        return (
          <TopicShelf
            key={topic.slug}
            id={topic.slug}
            topic={topic}
            title={topic.title}
            count={countLabel(matches.length, "course")}
          >
            <CourseGrid courses={matches.slice(0, shelfSize)} layout="shelf" />
          </TopicShelf>
        );
      })}
      {other.length ? (
        <TopicShelf
          id="more"
          title="More courses"
          count={countLabel(other.length, "course")}
        >
          <CourseGrid courses={other} />
        </TopicShelf>
      ) : null}
    </>
  );
}

function SearchResults({ search }: { search: string }) {
  const results = useContentSearch(search);
  const location = useLocation();
  const section = useRef<HTMLElement>(null);
  useEffect(() => {
    section.current?.focus({ preventScroll: true });
  }, [location.key]);
  const courseCount = results.matches.filter(
    (match) => match.kind === "course",
  ).length;
  const lessonCount = results.matches.length - courseCount;
  return (
    <section
      ref={section}
      tabIndex={-1}
      className="explore-shelf"
      aria-labelledby="explore-results-title"
    >
      <div className="explore-shelf-heading">
        <div>
          <h2 id="explore-results-title">
            {COURSE_CREATION_ENABLED
              ? "Find courses and lessons"
              : "Find lessons"}
          </h2>
          <p role="status" className="muted">
            {results.pending
              ? "Searching…"
              : COURSE_CREATION_ENABLED
                ? `${countLabel(courseCount, "course")}${lessonCount ? ` · ${countLabel(lessonCount, "lesson")}` : ""} found`
                : `${countLabel(lessonCount, "lesson")} found`}
          </p>
        </div>
        <Link className="explore-see-all" to="/explore">
          Clear search
        </Link>
      </div>
      {results.failed ? (
        <div className="status-panel">
          <p>Some results are unavailable. Please retry.</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={results.retry}
          >
            Retry search
          </button>
        </div>
      ) : null}
      <div className="library-search-results">
        {results.matches.map((match) => (
          <Link
            key={match.id}
            to={match.href}
            className="library-search-result"
          >
            <Thumbnail name={match.image} variant={match.kind} />
            <div>
              <h3>{match.title}</h3>
              <span className="muted small">{match.detail}</span>
            </div>
            <span aria-hidden="true">→</span>
          </Link>
        ))}
      </div>
      {!results.pending && !results.failed && !results.matches.length ? (
        <ExploreEmpty
          title={
            COURSE_CREATION_ENABLED
              ? "No courses or lessons found"
              : "No lessons found"
          }
          to="/explore"
          action={
            COURSE_CREATION_ENABLED
              ? "Show all courses →"
              : "Show all lessons →"
          }
        >
          {COURSE_CREATION_ENABLED
            ? "Try another title or clear your search to browse courses and lessons."
            : "Try another title or clear your search to browse lessons."}
        </ExploreEmpty>
      ) : null}
    </section>
  );
}
