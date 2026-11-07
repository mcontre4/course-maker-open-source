import { useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useApplication } from "../application-context";
import { CreatorAttribution } from "../CreatorLink";
import { ErrorNotice, PageHeading, QueryStatus } from "../components";
import { watchPath } from "./CreatorProfilePage";
import { CopyLessonButton } from "../CopyLessonButton";
import { LearnerLessonQuiz } from "../LearnerLessonQuiz";
import {
  LearnerInteractiveView,
  LessonPath,
  NextPart,
  interactiveParts,
  useLessonPart,
  usePausedWhenHidden,
  useTriedPrompts,
  type LessonPart,
} from "../interactives/LessonPath";
import { useLearnerInteractives } from "../lesson-interactive-context";

export function PublicLessonPage() {
  const { lessonId = "" } = useParams();
  const [params] = useSearchParams();
  const courseId = params.get("course") ?? undefined;
  const { creators: api, learnerQuizzes } = useApplication();
  const query = useQuery({
    queryKey: ["published-lesson", lessonId, courseId],
    queryFn: () => {
      if (!api)
        throw new Error("Published videos are unavailable in demo mode.");
      return api.watch(lessonId, courseId);
    },
  });
  const creatorId = query.data?.creator?.id;
  const catalog = useQuery({
    queryKey: ["creator", creatorId],
    enabled: !!creatorId && !!courseId,
    queryFn: () => api!.page(creatorId!),
  });
  const interactives = useLearnerInteractives(lessonId).data ?? [];
  // A course lesson's quiz belongs to the course, so only standalone lessons offer one here.
  const quizQuery = useQuery({
    queryKey: ["public-lesson-quiz", lessonId],
    queryFn: () => learnerQuizzes!.get(lessonId),
    enabled: !!learnerQuizzes && !courseId,
  });
  const quiz = quizQuery.data;
  const parts: readonly LessonPart[] = [
    {
      id: "video",
      title: "Watch",
      detail: query.data ? `${query.data.lesson.minutes} min video` : "Video",
    },
    ...interactiveParts(interactives),
    ...(quiz
      ? [
          {
            id: "quiz",
            title: "Check your understanding",
            detail: `${quiz.questions.length} question${quiz.questions.length === 1 ? "" : "s"}`,
          },
        ]
      : []),
  ];
  const { active, select } = useLessonPart(parts);
  const tried = useTriedPrompts();
  const videoSurface = useRef<HTMLDivElement>(null);
  usePausedWhenHidden(videoSurface, active !== "video");
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  const { lesson, creator } = query.data;
  const course = catalog.data?.courses.find((c) => c.id === courseId);
  return (
    <div
      className="watch-page"
      data-part={active === "video" ? "video" : "other"}
      data-in-course={!!course}
    >
      <PageHeading
        eyebrow={course?.title ?? "PUBLIC LESSON"}
        title={lesson.title}
      >
        {lesson.minutes} min
      </PageHeading>
      <div className="watch-meta">
        {creator && <CreatorAttribution creator={creator} />}
        <CopyLessonButton
          lessonId={lesson.id}
          courseId={courseId}
          title={lesson.title}
          image={lesson.image}
        />
      </div>
      {parts.length > 1 && (
        <LessonPath parts={parts} active={active} onSelect={select} />
      )}
      <div
        ref={videoSurface}
        className="watch-video"
        hidden={active !== "video"}
      >
        <video
          key={lesson.id + ":" + lesson.videoUrl}
          className="public-video"
          src={lesson.videoUrl ?? undefined}
          controls
          playsInline
          preload="metadata"
          aria-label={lesson.title}
        />
      </div>
      {interactives
        .filter((item) => item.id === active)
        .map((item) => (
          <LearnerInteractiveView
            key={item.id}
            interactive={item}
            checked={tried.checked(item.id)}
            onToggle={(index) => tried.toggle(item.id, index)}
          />
        ))}
      {/* Stays mounted, so looking back at the video never loses answers. */}
      {quiz && (
        <div hidden={active !== "quiz"}>
          <LearnerLessonQuiz key={lesson.id} lessonId={lesson.id} />
        </div>
      )}
      {!courseId && <ErrorNotice error={quizQuery.error} />}
      <NextPart parts={parts} active={active} onSelect={select} />
      {course && (
        <nav className="published-course" aria-label="Course lessons">
          <h2>{course.title}</h2>
          <ol>
            {course.lessons.map((item) => (
              <li key={item.id}>
                <Link
                  aria-current={item.id === lesson.id ? "page" : undefined}
                  to={watchPath(item)}
                >
                  {item.title}
                </Link>
              </li>
            ))}
          </ol>
        </nav>
      )}
    </div>
  );
}
