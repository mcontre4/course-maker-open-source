import { COURSE_CREATION_ENABLED } from "../feature-flags";
import { WorkspacePage } from "./WorkspacePage";
import {
  ErrorNotice,
  LinkButton,
  PageHeading,
  QueryStatus,
} from "../components";
import { useCourses } from "../application-context";
import { CourseCard } from "./HomePage";
import { continueItems } from "../home-feed";
import { HomeRail, WorkCard } from "../HomeShelves";
import { useLessons } from "../lesson-context";
import { isFinishedLesson } from "../lesson-workflow";
import { useLearningActivity } from "../use-learning-activity";

export function LibraryPage({ workspace = false }: { workspace?: boolean }) {
  return workspace ? <WorkspacePage /> : <Library />;
}
function Library() {
  const query = useCourses();
  const lessons = useLessons();
  const activity = useLearningActivity();
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  const courses = COURSE_CREATION_ENABLED
    ? query.data.filter((course) => course.status === "ready")
    : [];
  const lessonsPending = lessons.isPending || activity.isPending;
  const watchable = lessonsPending
    ? []
    : continueItems(
        [],
        (lessons.data ?? []).filter(isFinishedLesson),
        activity.data ?? [],
      );
  return (
    <div className="home">
      <PageHeading eyebrow="YOUR LEARNING" title="My library">
        The lessons you’ve started and can watch, in one place.
      </PageHeading>
      {courses.length ? (
        <section aria-labelledby="library-courses">
          <h2 id="library-courses" className="library-heading">
            Courses
          </h2>
          <div className="course-stack">
            {courses.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </section>
      ) : null}
      {watchable.length ? (
        <HomeRail title="Lessons" size="wide" count={watchable.length}>
          {watchable.map((item) => (
            <WorkCard key={item.id} item={item} />
          ))}
        </HomeRail>
      ) : null}
      {lessons.error ? <ErrorNotice error={lessons.error} /> : null}
      {courses.length ||
      watchable.length ||
      lessonsPending ||
      lessons.error ? null : (
        <div className="empty-state panel">
          <h2>Nothing to learn from yet</h2>
          <p className="muted">Create a lesson and it will show up here.</p>
          <LinkButton to="/lessons/new">Create a lesson →</LinkButton>
          {COURSE_CREATION_ENABLED ? (
            <LinkButton to="/courses/new" secondary>
              Create a course →
            </LinkButton>
          ) : null}
        </div>
      )}
    </div>
  );
}
