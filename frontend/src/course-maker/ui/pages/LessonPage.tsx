import { useRecordOpened } from "../use-learning-activity";
import { hasLessonArtifacts, lessonPlaybackUrl } from "../learning/lesson-view";
import { CopyLessonButton } from "../CopyLessonButton";
import { LessonInteractive } from "../learning/LessonInteractive";
import { CreatorLink } from "../CreatorLink";
import { QueryWorkspace } from "../components";
import { ActivityNotice } from "../activity";
import { ThumbnailPanel } from "../ThumbnailPanel";
import { useEffect, useRef, useState } from "react";
import { CourseMedia } from "../CourseMedia";
import { StylePanel } from "../StylePanel";
import { useGenerationMode } from "../generation-mode";
import { LessonPlan } from "../learning/LessonPlan";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button } from "../primitives/Button";
import type { CourseResponse, LessonResponse } from "../../application/dto";
import {
  useApplication,
  useCourse,
  useCourseMutation,
} from "../application-context";
import {
  ErrorNotice,
  LinkButton,
  PageHeading,
  QueryStatus,
} from "../components";
import { LessonNavigation } from "../learning/LessonNavigation";
import { LessonPlayer } from "../learning/LessonPlayer";
import { Quiz } from "../learning/Quiz";
import { LessonInteractivesPanel } from "../interactives/InteractiveList";
import {
  LearnerInteractiveView,
  LessonPath,
  NextPart,
  interactiveParts,
  liveInteractives,
  useLessonPart,
  usePausedWhenHidden,
  useTriedPrompts,
  type LessonPart,
} from "../interactives/LessonPath";
import {
  courseInteractiveHome,
  interactivePath,
} from "../interactives/interactive-paths";
import { useLessonInteractives } from "../lesson-interactive-context";

export function LessonPage() {
  const { courseId = "", lessonId = "" } = useParams();
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
  const lesson = query.data.chapters
    .flatMap((c) => c.lessons)
    .find((l) => l.id === lessonId);
  if (!lesson)
    return (
      <div className="status-panel">
        <h1>Lesson not found.</h1>
        <LinkButton to="/">Back to my learning</LinkButton>
      </div>
    );
  if (query.data.status === "draft")
    return (
      <div className="status-panel">
        <h1>Approve your syllabus to begin.</h1>
        <LinkButton to={"/courses/" + courseId + "/syllabus"}>
          Review syllabus
        </LinkButton>
      </div>
    );
  return (
    <QueryWorkspace
      error={query.error}
      retry={() => {
        void query.refetch();
      }}
    >
      <LessonWorkspace
        key={courseId + ":" + lessonId}
        course={query.data}
        lesson={lesson}
      />
    </QueryWorkspace>
  );
}

function LessonWorkspace({
  course,
  lesson,
}: {
  course: CourseResponse;
  lesson: LessonResponse;
}) {
  const app = useApplication();
  const [generationMode, setGenerationMode] = useGenerationMode(
    "course-lesson:" + course.id + ":" + lesson.id,
    "course:" + course.id,
  );
  const [styleBusy, setStyleBusy] = useState(false);
  const [styleDirty, setStyleDirty] = useState(false);
  const [mediaBusy, setMediaBusy] = useState(false);
  const [planBusy, setPlanBusy] = useState(false);
  const review = useCourseMutation(
    app.reviewLesson.execute.bind(app.reviewLesson),
  );
  const [params, setParams] = useSearchParams();
  const quiz = params.get("quiz") === "1";
  const ready = hasLessonArtifacts(lesson);
  const editing = params.get("edit") === "1";
  const studio = !ready || editing;
  const chapter = course.chapters.find((c) =>
    c.lessons.some((l) => l.id === lesson.id),
  )!;
  const reviewed = course.reviewed.includes(lesson.id);
  const interactiveHome = courseInteractiveHome(course.id, lesson.id);
  const inLesson = liveInteractives(
    useLessonInteractives(lesson.id).data ?? [],
  );
  const parts: readonly LessonPart[] = [
    { id: "video", title: "Watch", detail: "Lesson video" },
    ...interactiveParts(inLesson),
  ];
  const { active: part, select: selectPart } = useLessonPart(parts);
  const viewing = studio ? "video" : part;
  const tried = useTriedPrompts();
  const mediaSurface = useRef<HTMLDivElement>(null);
  usePausedWhenHidden(mediaSurface, viewing !== "video");
  // Coming back from an interactive lands on the list, not the top of a long page.
  useEffect(() => {
    if (globalThis.location?.hash === "#lesson-interactives")
      document.getElementById("lesson-interactives")?.scrollIntoView?.();
  }, []);
  return (
    <>
      <Link className="back-link" to="/">
        ← My learning <span>/ {course.title}</span>
      </Link>
      <ActivityNotice
        operation={course.activeOperation}
        error={course.operationError}
      />
      {ready && !quiz && (
        <div className="lesson-view-toolbar">
          <p className="muted small">
            {studio ? "Editing lesson" : "Lesson preview"}
          </p>
          <Button
            variant="secondary"
            disabled={
              studio &&
              (!!course.activeOperation ||
                styleBusy ||
                styleDirty ||
                mediaBusy ||
                planBusy)
            }
            onClick={() => {
              setParams((current) => {
                const next = new URLSearchParams(current);
                if (editing) next.delete("edit");
                else next.set("edit", "1");
                return next;
              });
            }}
          >
            {studio ? "View lesson" : "Edit lesson"}
          </Button>
        </div>
      )}
      <div className="lesson-grid">
        <div className="lesson-main">
          {quiz ? (
            <Quiz
              course={course}
              lesson={lesson}
              onBack={() => setParams({})}
            />
          ) : (
            <>
              {!studio && app.interactives && (
                <LessonPath
                  parts={parts}
                  active={part}
                  onSelect={selectPart}
                  add={{
                    to: interactivePath(interactiveHome, "new"),
                    label: "Add an interactive",
                    detail: "Let learners try it",
                  }}
                />
              )}
              <div ref={mediaSurface} hidden={viewing !== "video"}>
                <LessonPlayer
                  key={lesson.id}
                  courseId={course.id}
                  lesson={{
                    ...lesson,
                    videoUrl: lessonPlaybackUrl(lesson, course.id),
                  }}
                  courseTitle={course.title}
                  watched={reviewed}
                  pending={review.isPending}
                  onWatched={() =>
                    review.mutate({ courseId: course.id, lessonId: lesson.id })
                  }
                />
                <LessonInteractive
                  interactive={lesson.interactive}
                  editing={studio}
                />
              </div>
              {!studio &&
                inLesson
                  .filter((item) => item.id === part)
                  .map((item) => (
                    <LearnerInteractiveView
                      key={item.id}
                      interactive={item}
                      checked={tried.checked(item.id)}
                      onToggle={(index) => tried.toggle(item.id, index)}
                      action={
                        <LinkButton
                          secondary
                          to={interactivePath(interactiveHome, item.id)}
                        >
                          Edit interactive
                        </LinkButton>
                      }
                    />
                  ))}
              {!studio && (
                <NextPart parts={parts} active={part} onSelect={selectPart} />
              )}
              {studio && app.interactives && (
                <div className="panel" id="lesson-interactives">
                  <LessonInteractivesPanel
                    lesson={{
                      lessonId: lesson.id,
                      title: lesson.title,
                      topics: lesson.topics,
                    }}
                    home={interactiveHome}
                  />
                </div>
              )}
              {studio && (
                <>
                  <ThumbnailPanel
                    id={course.id}
                    kind="course"
                    lessonId={lesson.id}
                    image={lesson.image}
                    disabled={reviewed || styleDirty}
                  />
                  <StylePanel
                    id={course.id}
                    kind="course"
                    lessonId={lesson.id}
                    style={lesson.style}
                    inherited={course.style}
                    history={lesson.styleHistory}
                    generationMode={generationMode}
                    disabled={
                      !!course.activeOperation ||
                      reviewed ||
                      mediaBusy ||
                      planBusy
                    }
                    onBusyChange={setStyleBusy}
                    onDirtyChange={setStyleDirty}
                  />
                  <LessonPlan
                    key={lesson.id}
                    courseId={course.id}
                    lesson={lesson}
                    disabled={
                      !!course.activeOperation ||
                      styleBusy ||
                      styleDirty ||
                      mediaBusy
                    }
                    mode={generationMode}
                    onModeChange={setGenerationMode}
                    onBusyChange={setPlanBusy}
                  />
                  <CourseMedia
                    course={course}
                    lesson={lesson}
                    disabled={
                      !!course.activeOperation ||
                      reviewed ||
                      styleBusy ||
                      styleDirty ||
                      planBusy
                    }
                    mode={generationMode}
                    onModeChange={setGenerationMode}
                    onBusyChange={setMediaBusy}
                  />
                </>
              )}
              <PageHeading
                eyebrow={chapter.title.toUpperCase()}
                title={lesson.title}
              >
                A small step toward something you can use.
              </PageHeading>
              <CopyLessonButton
                lessonId={lesson.id}
                courseId={course.id}
                title={lesson.title}
                image={lesson.image}
              />
              <CreatorLink id={course.ownerId} />
              <section className="lesson-coverage">
                <h2>In this lesson</h2>
                <ul>
                  {lesson.topics.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </section>
              <ErrorNotice error={review.error} />
              <section className="quiz-invitation sage">
                <h2>Make it stick.</h2>
                <p>
                  Finish with {lesson.quiz.length} quick questions about this
                  lesson.
                </p>
                <Button
                  disabled={
                    !!course.activeOperation ||
                    !reviewed ||
                    !ready ||
                    !lesson.quiz.length
                  }
                  onClick={() => setParams({ quiz: "1" })}
                >
                  Take the lesson quiz →
                </Button>
                <p className="small">
                  {reviewed
                    ? "A lesson is complete when you finish its video and pass the quiz."
                    : ready
                      ? "Finish watching the video to unlock the quiz."
                      : "The quiz will unlock after your video is ready and you’ve watched it."}
                </p>
              </section>
            </>
          )}
        </div>
        <LessonNavigation course={course} selected={lesson.id} />
      </div>
    </>
  );
}
