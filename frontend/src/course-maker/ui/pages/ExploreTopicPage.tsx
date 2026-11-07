import { Link, useParams, useSearchParams } from "react-router-dom";
import { LinkButton, QueryStatus } from "../components";
import { topicBySlug, topicPath, type CourseTopic } from "../course-catalog";
import { countLabel, coursesInTopic, lessonsInTopic } from "../explore-courses";
import {
  CourseGrid,
  ExploreEmpty,
  ExploreHero,
  LessonGrid,
  SubtopicTabs,
  TopicTabs,
  exploreAllLabel,
} from "../explore";
import { COURSE_CREATION_ENABLED } from "../feature-flags";
import { useDiscovery } from "../use-discovery";

export function ExploreTopicPage() {
  const { topicSlug } = useParams();
  const [params] = useSearchParams();
  const discovery = useDiscovery();
  const topic = topicBySlug(topicSlug);
  if (!topic)
    return (
      <div className="status-panel">
        <h1>We couldn’t find that topic.</h1>
        <LinkButton to="/explore">
          {COURSE_CREATION_ENABLED
            ? "Browse all courses"
            : "Browse all lessons"}
        </LinkButton>
      </div>
    );
  const requested = params.get("sub");
  const subtopic = topic.subtopics.find((item) => item === requested);
  const loaded =
    discovery.data ??
    (discovery.isFetching || discovery.error
      ? undefined
      : { courses: [], lessons: [] });
  const noun = COURSE_CREATION_ENABLED ? "course" : "lesson";
  // Items are courses, or lessons while courses are hidden.
  const courses = COURSE_CREATION_ENABLED ? (loaded?.courses ?? []) : [];
  const lessons = COURSE_CREATION_ENABLED ? [] : (loaded?.lessons ?? []);
  const countIn = (inTopic?: CourseTopic, inSubtopic?: string) =>
    !inTopic
      ? courses.length + lessons.length
      : coursesInTopic(courses, inTopic, inSubtopic).length +
        lessonsInTopic(lessons, inTopic, inSubtopic).length;
  const courseMatches = coursesInTopic(courses, topic, subtopic);
  const lessonMatches = lessonsInTopic(lessons, topic, subtopic);
  const matchCount = courseMatches.length + lessonMatches.length;
  const label = subtopic ?? topic.title;
  return (
    <div className="explore">
      <ExploreHero topic={topic} title={topic.title}>
        {topic.blurb}
      </ExploreHero>
      <TopicTabs
        count={loaded ? (item) => countIn(item) : undefined}
        current={topic}
      />
      <SubtopicTabs
        topic={topic}
        count={loaded ? (item) => countIn(topic, item) : undefined}
        current={subtopic}
      />
      {discovery.error || (discovery.isFetching && !loaded) ? (
        <QueryStatus
          pending={discovery.isFetching}
          error={discovery.error}
          retry={() => void discovery.refetch()}
        />
      ) : null}
      {loaded ? (
        <section
          className="explore-shelf"
          aria-labelledby="topic-courses-title"
        >
          <div className="explore-shelf-heading">
            <div>
              <h2 id="topic-courses-title">
                {label} {noun}s
              </h2>
              <p role="status" className="muted">
                {countLabel(matchCount, noun)}
              </p>
            </div>
            {subtopic ? (
              <Link className="explore-see-all" to={topicPath(topic)}>
                Show all {topic.title}
              </Link>
            ) : null}
          </div>
          {matchCount ? (
            COURSE_CREATION_ENABLED ? (
              <CourseGrid courses={courseMatches} />
            ) : (
              <LessonGrid lessons={lessonMatches} />
            )
          ) : (
            <ExploreEmpty
              title={`No ${label} ${noun}s yet`}
              to={subtopic ? topicPath(topic) : "/explore"}
              action={
                subtopic
                  ? `Show all ${topic.title} →`
                  : `Browse ${exploreAllLabel.toLowerCase()} →`
              }
            >
              {COURSE_CREATION_ENABLED
                ? "Courses that creators publish on this topic show up here."
                : "Lessons that creators publish on this topic show up here."}
            </ExploreEmpty>
          )}
        </section>
      ) : null}
    </div>
  );
}
