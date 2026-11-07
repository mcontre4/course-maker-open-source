import { COURSE_CREATION_ENABLED } from "../feature-flags";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useApplication } from "../application-context";
import { useOwnCreator } from "../CreatorLink";
import { Avatar } from "../profile-context";
import { LinkButton, QueryStatus, Thumbnail } from "../components";
import type {
  PublishedCourse,
  PublishedLesson,
} from "../../application/creators";

export function watchPath(lesson: PublishedLesson) {
  return (
    "/watch/lessons/" +
    lesson.id +
    (lesson.courseId ? "?course=" + lesson.courseId : "")
  );
}

function plural(count: number, word: string) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}
const minutesOf = (lessons: readonly PublishedLesson[]) =>
  lessons.reduce((total, lesson) => total + lesson.minutes, 0);

function ShareProfileButton() {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => {
    if (state === "idle") return;
    const timer = window.setTimeout(() => setState("idle"), 2400);
    return () => window.clearTimeout(timer);
  }, [state]);
  return (
    <>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => {
          navigator.clipboard
            .writeText(window.location.href)
            .then(() => setState("copied"))
            .catch(() => setState("failed"));
        }}
      >
        <svg className="btn-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" />
          <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />
        </svg>
        {state === "copied" ? "Link copied" : "Copy profile link"}
      </button>
      <span className="sr-only" role="status">
        {state === "copied"
          ? "Profile link copied"
          : state === "failed"
            ? "Couldn’t copy the link. Copy it from the address bar."
            : ""}
      </span>
    </>
  );
}

function LessonGrid({ lessons }: { lessons: readonly PublishedLesson[] }) {
  return (
    <div className="discovery-grid">
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

function CourseCard({ course }: { course: PublishedCourse }) {
  const first = course.lessons[0];
  return (
    <article className="creator-course">
      <div className="creator-course-cover">
        <Thumbnail name={course.image} variant="course" />
      </div>
      <div className="creator-course-body">
        <h3>{course.title}</h3>
        {course.description ? (
          <p className="muted">{course.description}</p>
        ) : null}
        <p className="creator-course-meta">
          {plural(course.lessons.length, "lesson")}
          <span>{minutesOf(course.lessons)} min in total</span>
        </p>
        {first ? (
          <LinkButton to={watchPath(first)}>Start course</LinkButton>
        ) : null}
      </div>
      {course.lessons.length ? (
        <ol
          className="creator-course-lessons"
          aria-label={"Lessons in " + course.title}
        >
          {course.lessons.map((lesson, index) => (
            <li key={lesson.id}>
              <Link to={watchPath(lesson)}>
                <b aria-hidden="true">{index + 1}</b>
                <span>{lesson.title}</span>
                <span className="muted small">{lesson.minutes} min</span>
              </Link>
            </li>
          ))}
        </ol>
      ) : null}
    </article>
  );
}

export function CreatorProfilePage() {
  const { creatorId = "" } = useParams();
  const api = useApplication().creators;
  const own = useOwnCreator().data?.id === creatorId;
  const query = useQuery({
    queryKey: ["creator", creatorId],
    queryFn: () => {
      if (!api)
        throw new Error("Public profiles are unavailable in demo mode.");
      return api.page(creatorId);
    },
  });
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  const { creator, lessons, courses: allCourses } = query.data;
  const courses = COURSE_CREATION_ENABLED ? allCourses : [];
  const all = [...lessons, ...courses.flatMap((course) => course.lessons)];
  const minutes = minutesOf(all);
  return (
    <div className="creator-page">
      <header className="creator-hero">
        <Avatar name={creator.name} picture={creator.picture} large />
        <div className="creator-hero-copy">
          <h1>{creator.name}</h1>
          {all.length ? (
            <p className="creator-stats">
              <span>
                <strong>{all.length}</strong>{" "}
                {all.length === 1 ? "video" : "videos"}
              </span>
              {courses.length ? (
                <span>
                  <strong>{courses.length}</strong>{" "}
                  {courses.length === 1 ? "course" : "courses"}
                </span>
              ) : null}
              {minutes ? (
                <span>
                  <strong>{minutes}</strong> min to watch
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
        <div className="creator-hero-actions">
          {own ? (
            <LinkButton to="/settings" secondary>
              Edit profile
            </LinkButton>
          ) : null}
          <ShareProfileButton />
        </div>
      </header>
      {courses.length ? (
        <section aria-labelledby="published-courses">
          <div className="home-section-heading">
            <h2 id="published-courses">Courses</h2>
          </div>
          <div className="creator-courses">
            {courses.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </section>
      ) : null}
      {lessons.length ? (
        <section aria-labelledby="published-lessons">
          <div className="home-section-heading">
            <h2 id="published-lessons">Lessons</h2>
          </div>
          <LessonGrid lessons={lessons} />
        </section>
      ) : null}
      {!all.length ? (
        <div className="workspace-empty">
          <h2>
            {own
              ? "You haven’t published anything yet"
              : "Nothing published yet"}
          </h2>
          <p className="muted">
            {own
              ? "Finished lessons you publish appear here, where anyone with the link can watch them."
              : `When ${creator.name} publishes lessons, they appear here.`}
          </p>
          {own ? (
            <LinkButton to="/workspace">Go to My creations</LinkButton>
          ) : (
            <LinkButton to="/explore" secondary>
              Explore courses
            </LinkButton>
          )}
        </div>
      ) : null}
    </div>
  );
}
