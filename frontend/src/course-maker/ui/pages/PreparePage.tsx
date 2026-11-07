import { useRecordOpened } from "../use-learning-activity";
import { useParams } from "react-router-dom";
import { useCourse } from "../application-context";
import {
  LinkButton,
  PageHeading,
  QueryStatus,
  Spark,
  Thumbnail,
} from "../components";

export function PreparePage() {
  const { courseId = "" } = useParams();
  const query = useCourse(courseId);
  useRecordOpened(query.data?.id);
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    );
  const course = query.data;
  if (course.status === "draft")
    return (
      <div className="status-panel">
        <h1>Your syllabus needs approval first.</h1>
        <LinkButton to={"/courses/" + course.id + "/syllabus"}>
          Review syllabus →
        </LinkButton>
      </div>
    );
  const first = course.chapters[0].lessons[0];
  return (
    <>
      <PageHeading
        eyebrow="YOUR SYLLABUS IS APPROVED"
        title="Your syllabus is approved."
      >
        {course.title} · Chapter 1 · Lesson 1
      </PageHeading>
      <section className="prepared lavender">
        <Spark />
        <h2>From curiosity to your first “aha”.</h2>
        <p>
          Your course plan is saved. Each lesson will have a video to watch,
          followed by a short quiz.
        </p>
        <p className="muted small">
          Open your first lesson to generate its teaching plan. Video and quiz
          generation are not connected yet.
        </p>
        <LinkButton to="/" secondary>
          Back to my learning
        </LinkButton>
      </section>
      <section className="ready-card sage">
        <Thumbnail name={first.image} variant="chapter" />
        <div>
          <p className="eyebrow">YOUR FIRST LESSON</p>
          <h2>{first.title}</h2>
          <p>
            {first.minutes} minutes of planned video ·{" "}
            {first.quiz.length
              ? `${first.quiz.length}-question quiz`
              : "Quiz content not available yet"}
          </p>
        </div>
        <LinkButton to={"/courses/" + course.id + "/lessons/" + first.id}>
          {first.videoUrl ? "Watch first lesson →" : "View first lesson →"}
        </LinkButton>
      </section>
    </>
  );
}
