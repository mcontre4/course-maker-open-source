import { COURSE_CREATION_ENABLED } from "../feature-flags";
import { useCourses } from "../application-context";
import {
  Books,
  CourseIcon,
  ErrorNotice,
  LessonIcon,
  LinkButton,
  Progress,
  QueryStatus,
  Summary,
  Thumbnail,
} from "../components";
import type { CourseResponse } from "../../application/dto";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { legacyExploreUrl } from "../course-search";
import { continueItems, newestPublicLessons } from "../home-feed";
import {
  BrowseTopics,
  HomeFeature,
  HomeFeatureSkeleton,
  HomeRail,
  PublicCourseCard,
  PublicLessonCard,
  SkeletonCards,
  WorkCard,
} from "../HomeShelves";
import { useLessons } from "../lesson-context";
import { useDiscovery } from "../use-discovery";
import { useLearningActivity } from "../use-learning-activity";
import { useSignedIn } from "../authentication";
import { watchPath } from "./CreatorProfilePage";

export function CourseCard({ course }: { course: CourseResponse }) {
  const lessons = course.chapters.flatMap((c) => c.lessons);
  const next = lessons.find((l) => !course.completed.includes(l.id));
  const finished = lessons.length > 0 && !next;
  const resume = next ?? lessons[0];
  const percent = Math.round(
    (course.completed.length / Math.max(1, lessons.length)) * 100,
  );
  return (
    <article className="course-card">
      <div className="course-card-cover">
        <Thumbnail name={course.image} variant="course" />
      </div>
      <div className="course-card-body">
        <span
          className="workflow-status"
          data-tone={finished ? "ready" : "progress"}
        >
          {finished ? "Completed" : "In progress"}
        </span>
        <h3>{course.title}</h3>
        <p className="course-card-description muted">{course.description}</p>
        <Summary course={course} />
        <div className="course-card-progress">
          <Progress
            completed={course.completed.length}
            total={lessons.length}
          />
          <p className="progress-label">
            {course.completed.length} of {lessons.length} lessons complete ·{" "}
            {percent}%
          </p>
        </div>
      </div>
      <div className="course-card-next">
        {next ? (
          <p className="small">
            <span className="muted">Up next</span>
            <strong>{next.title}</strong>
          </p>
        ) : null}
        <LinkButton
          to={
            resume
              ? "/courses/" + course.id + "/lessons/" + resume.id
              : "/courses/" + course.id + "/syllabus"
          }
        >
          {finished ? "Review course" : "Continue learning"}
        </LinkButton>
      </div>
    </article>
  );
}

function CreateHero({
  firstTime,
  returning,
  guest = false,
}: {
  firstTime: boolean;
  returning: boolean;
  guest?: boolean;
}) {
  return (
    <section
      className="home-hero"
      data-returning={returning}
      aria-labelledby="home-title"
    >
      <div className="home-hero-intro">
        <h1 id="home-title">What would you like to learn next?</h1>
        <p>
          Describe an idea and your guide drafts an outline. You review it, then
          it becomes a narrated, animated video.
        </p>
      </div>
      <Books />
      <div className="home-create-options">
        <article className="home-create-option">
          <div className="home-create-top">
            <span className="home-create-icon lavender">
              <LessonIcon />
            </span>
            <p className="home-create-meta">1 to 10 minutes</p>
          </div>
          <h2>A single lesson</h2>
          <p>One topic, explained in a short video you can edit and share.</p>
          <Link className="btn btn-primary" to="/lessons/new">
            Create a lesson
          </Link>
          {guest ? (
            <p className="home-create-note">
              No account needed to watch. Sign in to create.
            </p>
          ) : null}
        </article>
        {COURSE_CREATION_ENABLED ? (
          <article className="home-create-option">
            <div className="home-create-top">
              <span className="home-create-icon sage">
                <CourseIcon />
              </span>
              <p className="home-create-meta">A few hours, or a few weeks</p>
            </div>
            <h2>A full course</h2>
            <p>Chapters of lessons with quizzes, paced to fit your schedule.</p>
            <Link className="btn btn-primary" to="/courses/new">
              {firstTime ? "Create your first course" : "Create a course"}
            </Link>
          </article>
        ) : null}
      </div>
      <ol className="home-steps" aria-label="How it works">
        <li>
          <b>1</b>
          <span>
            Describe your idea
            <small>A title and what you want to learn</small>
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
            Watch and refine
            <small>Ready in a few minutes</small>
          </span>
        </li>
      </ol>
    </section>
  );
}

export function HomePage() {
  const [params] = useSearchParams();
  const legacy = legacyExploreUrl(params);
  return legacy ? <Navigate to={legacy} replace /> : <Home />;
}

function Home() {
  // Anyone can look around. Visitors without an account skip the requests for
  // private work and see the public lessons instead.
  const signedIn = useSignedIn();
  const query = useCourses(signedIn);
  const lessons = useLessons(signedIn);
  const activity = useLearningActivity(signedIn);
  const discovery = useDiscovery();
  if (signedIn && !query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    );
  const workPending = signedIn && (lessons.isPending || activity.isPending);
  const work =
    workPending || !signedIn
      ? []
      : continueItems(
          COURSE_CREATION_ENABLED ? (query.data ?? []) : [],
          lessons.data ?? [],
          activity.data ?? [],
        );
  const resume = work.find((item) => item.unfinished);
  const otherWork = work.filter((item) => item !== resume).slice(0, 12);
  const publicLessons = newestPublicLessons(discovery.data?.lessons ?? []);
  const newest = !workPending && !resume ? publicLessons[0] : undefined;
  const lessonRow = publicLessons.filter((lesson) => lesson !== newest);
  const courseRow = COURSE_CREATION_ENABLED
    ? (discovery.data?.courses ?? [])
    : [];
  const discoveryPending = discovery.isFetching && !discovery.data;
  return (
    <div className="home">
      <CreateHero
        firstTime={!query.data?.length}
        returning={work.length > 0}
        guest={!signedIn}
      />
      {workPending ? <HomeFeatureSkeleton /> : null}
      {resume ? (
        <HomeFeature
          eyebrow="Continue where you left off"
          title={resume.title}
          detail={resume.detail}
          image={resume.image}
          variant={resume.variant}
          to={resume.to}
          action={resume.action}
          progress={resume.progress}
          status={resume.status}
          priority
        />
      ) : null}
      {newest ? (
        <HomeFeature
          eyebrow="Newest lesson"
          title={newest.title}
          detail={newest.minutes + " min lesson"}
          image={newest.image}
          variant="lesson"
          to={watchPath(newest)}
          action="Watch lesson"
        />
      ) : null}
      {signedIn && lessons.error ? <ErrorNotice error={lessons.error} /> : null}
      {otherWork.length ? (
        <HomeRail
          title={resume ? "More of your work" : "Your work"}
          link={{ to: "/workspace", label: "See all your work" }}
          size="wide"
          count={otherWork.length}
        >
          {otherWork.map((item) => (
            <WorkCard key={item.id} item={item} />
          ))}
        </HomeRail>
      ) : null}
      {discovery.error && !discovery.data ? (
        <section className="home-rail" aria-labelledby="home-newest-error">
          <div className="home-rail-heading">
            <h2 id="home-newest-error">Newest lessons</h2>
          </div>
          <div className="home-rail-error">
            <p className="muted">New lessons couldn’t load.</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void discovery.refetch()}
            >
              Try again
            </button>
          </div>
        </section>
      ) : null}
      {discoveryPending || lessonRow.length ? (
        <HomeRail
          title="Newest lessons"
          link={{ to: "/explore", label: "See all" }}
          count={lessonRow.length}
        >
          {discoveryPending ? (
            <SkeletonCards />
          ) : (
            lessonRow.map((lesson) => (
              <PublicLessonCard key={lesson.id} lesson={lesson} />
            ))
          )}
        </HomeRail>
      ) : null}
      {courseRow.length ? (
        <HomeRail
          title="Newest courses"
          link={{ to: "/explore", label: "See all" }}
          count={courseRow.length}
        >
          {courseRow.map((course) => (
            <PublicCourseCard key={course.id} course={course} />
          ))}
        </HomeRail>
      ) : null}
      {COURSE_CREATION_ENABLED ? <BrowseTopics /> : null}
    </div>
  );
}
