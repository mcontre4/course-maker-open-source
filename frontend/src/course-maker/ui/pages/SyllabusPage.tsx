import { useRecordOpened } from "../use-learning-activity";
import { ComposerPrimitive } from "@assistant-ui/react";
import { AgentMessages, AgentThread } from "../assistant/AgentThread";
import { GuidePanel } from "../GuidePanel";
import { CreatorLink } from "../CreatorLink";
import { QueryWorkspace } from "../components";
import { ActivityNotice } from "../activity";
import { ThumbnailPanel } from "../ThumbnailPanel";
import { StylePanel } from "../StylePanel";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import type { GenerationMode } from "../../application/generation-mode";
import { QualitySettings } from "../GenerationModeSelector";
import { useGenerationMode } from "../generation-mode";
import { Button } from "../primitives/Button";
import type {
  CourseResponse,
  GenerateSyllabusRequest,
} from "../../application/dto";
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
  Spark,
  Summary,
} from "../components";

export function SyllabusPage() {
  const { courseId = "" } = useParams();
  const query = useCourse(courseId);
  useRecordOpened(query.data?.id);
  const location = useLocation();
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
  const initialMessage =
    typeof location.state?.initialMessage === "string"
      ? location.state.initialMessage
      : undefined;
  return (
    <QueryWorkspace
      error={query.error}
      retry={() => {
        void query.refetch();
      }}
    >
      <SyllabusWorkspace
        key={query.data.id}
        course={query.data}
        initialMessage={initialMessage}
        initialMode={location.state?.generationMode}
      />
    </QueryWorkspace>
  );
}

function SyllabusWorkspace({
  course,
  initialMessage,
  initialMode,
}: {
  course: CourseResponse;
  initialMessage?: string;
  initialMode?: GenerationMode;
}) {
  const app = useApplication();
  const [guideBusy, setGuideBusy] = useState(false);
  const [generationMode, setGenerationMode] = useGenerationMode(
    "course:" + course.id,
    undefined,
    initialMode,
  );
  const navigate = useNavigate();
  const edit = useCourseMutation(app.editTopic.execute.bind(app.editTopic));
  const approval = useCourseMutation(
    app.approveSyllabus.execute.bind(app.approveSyllabus),
  );
  const generation = useCourseMutation((request: GenerateSyllabusRequest) => {
    if (!app.generateSyllabus)
      throw new Error("The course guide is not configured.");
    return app.generateSyllabus.execute({
      ...request,
      sessionId: request.sessionId ?? course.syllabus?.sessionId,
      generationMode,
    });
  });
  const lessons = course.chapters.flatMap((ch) => ch.lessons);
  const [selectedLesson, setSelectedLesson] = useState(lessons[0]?.id ?? "");
  const selected = lessons.some((ls) => ls.id === selectedLesson)
    ? selectedLesson
    : (lessons[0]?.id ?? "");
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState(
    !lessons.length && !course.messages.length ? course.description : "",
  );
  const initialStarted = useRef(false);
  useEffect(() => {
    if (!initialMessage || initialStarted.current || !app.generateSyllabus)
      return;
    initialStarted.current = true;
    // Clear one-shot navigation intent before sending; reload must never resubmit it.
    navigate(`/courses/${course.id}/syllabus`, { replace: true, state: null });
    if (
      course.activeOperation ||
      course.messages.length ||
      (course.syllabus?.revision ?? 0) !== 0
    )
      return;
    generation.mutate(
      { courseId: course.id, message: initialMessage, expectedRevision: 0 },
      { onSuccess: () => setMessage("") },
    );
  }, [
    initialMessage,
    app.generateSyllabus,
    course.id,
    course.messages.length,
    course.syllabus?.revision,
    generation.mutate,
    navigate,
  ]);
  const conversation = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = conversation.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [course.messages.length, generation.isPending]);
  const draft = course.status === "draft";
  const [styleBusy, setStyleBusy] = useState(false);
  const [styleDirty, setStyleDirty] = useState(false);
  const generationPending =
    generation.isPending ||
    !!course.activeOperation?.includes("syllabus/generate");
  const contentBusy =
    !!course.activeOperation ||
    edit.isPending ||
    approval.isPending ||
    generation.isPending;
  const busy = contentBusy || styleBusy || styleDirty || guideBusy;
  const live = !!app.generateSyllabus;
  return (
    <>
      <Link className="back-link" to="/">
        ← My learning
      </Link>
      <ActivityNotice
        operation={course.activeOperation}
        error={course.operationError}
      />
      <PageHeading
        eyebrow="01  COURSE DETAILS    /    02  YOUR SYLLABUS"
        title="A learning path, made for you."
      >
        Review the outline. Ask your guide to refine it, or edit individual
        topics.
      </PageHeading>
      <CreatorLink id={course.ownerId} />
      <div className="syllabus-grid">
        <section
          className="panel syllabus-panel"
          aria-labelledby="syllabus-title"
        >
          <span className="pill lavender">
            {draft ? "DRAFT SYLLABUS" : "APPROVED SYLLABUS"}
          </span>
          <h2 id="syllabus-title">{course.title}</h2>
          <Summary course={course} />
          <ThumbnailPanel
            id={course.id}
            kind="course"
            image={course.image}
            disabled={false}
          />
          <StylePanel
            id={course.id}
            kind="course"
            style={course.style}
            history={course.styleHistory}
            generationMode={generationMode}
            disabled={contentBusy}
            onBusyChange={setStyleBusy}
            onDirtyChange={setStyleDirty}
          />
          {busy ? (
            <div className="syllabus-working" role="status" aria-atomic="true">
              <span className="syllabus-working-icon" aria-hidden="true">
                <Spark />
              </span>
              <div>
                <p className="syllabus-working-title">
                  {approval.isPending
                    ? "Saving your syllabus…"
                    : lessons.length
                      ? "Updating your syllabus…"
                      : "Creating your syllabus…"}
                </p>
                <p className="syllabus-working-description">
                  {generationPending
                    ? lessons.length
                      ? "Your guide is refining the plan. Your updated outline will appear here."
                      : "Your guide is shaping your learning path. Your outline will appear here."
                    : "Your changes are being saved."}
                </p>
                {generationPending ? (
                  <p className="syllabus-working-note">
                    Research and planning can take up to two minutes.
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
          <p className="muted small">
            {course.chapters.length} chapters · Video, practice, reading, and
            review
          </p>
          {course.syllabus?.warnings.map((warning, index) => (
            <p className="message" key={index}>
              {warning}
            </p>
          ))}
          {course.syllabus?.outcomes.length ? (
            <div>
              <h3>What you’ll learn</h3>
              <ul>
                {course.syllabus.outcomes.map((outcome, index) => (
                  <li key={index}>{outcome}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <hr />
          {lessons.length ? (
            <p className="progress-label">
              {lessons.length} lesson outlines · Explore each chapter below
            </p>
          ) : generationPending ? (
            <div className="syllabus-skeleton" aria-hidden="true">
              {[0, 1, 2].map((index) => (
                <div className="syllabus-skeleton-row" key={index}>
                  <span className="syllabus-skeleton-number" />
                  <div>
                    <span className="syllabus-skeleton-line" />
                    <span className="syllabus-skeleton-line short" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <h3>Your draft is saved.</h3>
              <p className="muted">
                Your outline will appear here. Send your request to the course
                guide to build or clarify your syllabus.
              </p>
            </div>
          )}
          {lessons.length ? (
            <div
              className="syllabus-scroll"
              tabIndex={0}
              aria-label="Detailed syllabus"
              aria-busy={busy}
            >
              {course.chapters.map((chapter, index) => (
                <details
                  className="chapter-outline"
                  key={chapter.id}
                  open={index === 0}
                >
                  <summary>
                    <span className="eyebrow">CHAPTER {index + 1}</span>
                    <h3>{chapter.title}</h3>
                    <span className="muted small">
                      {chapter.lessons.length} lessons{" "}
                      <span aria-hidden="true">⌄</span>
                    </span>
                  </summary>
                  <p className="muted">{chapter.summary}</p>
                  {chapter.lessons.map((lesson, lessonIndex) => {
                    const plan = course.syllabus?.lessons.find(
                      (item) => item.id === lesson.id,
                    );
                    return (
                      <article className="lesson-outline" key={lesson.id}>
                        <h4>
                          {lessonIndex + 1}. {lesson.title}
                        </h4>
                        <p className="muted small">
                          {plan ? `Week ${plan.week} · ` : ""}
                          {lesson.minutes} minutes{" "}
                          {live
                            ? "of video"
                            : "including video, practice & quiz"}
                        </p>
                        {plan ? (
                          <p className="muted small">
                            Practice {plan.practiceMinutes} min · Reading{" "}
                            {plan.readingMinutes} min · Review{" "}
                            {plan.reviewMinutes} min
                          </p>
                        ) : null}
                        {plan?.objectives.length ? (
                          <p className="small">
                            <strong>Learning objectives: </strong>
                            {plan.objectives.join(" · ")}
                          </p>
                        ) : null}
                        <ul>
                          {lesson.topics.map((item, topicIndex) => (
                            <li key={topicIndex}>
                              <span>{item}</span>
                              {draft ? (
                                <button
                                  className="remove-topic"
                                  disabled={busy || lesson.topics.length === 1}
                                  aria-label={"Remove topic: " + item}
                                  title={
                                    lesson.topics.length === 1
                                      ? "Keep at least one topic"
                                      : "Remove topic"
                                  }
                                  onClick={() =>
                                    edit.mutate({
                                      courseId: course.id,
                                      lessonId: lesson.id,
                                      topic: item,
                                      operation: "remove",
                                    })
                                  }
                                >
                                  ×
                                </button>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                        <p className="quiz-caption">
                          {lesson.quiz.length
                            ? `QUIZ · ${lesson.quiz.length} questions after this lesson`
                            : "Lesson content will be created after syllabus approval."}
                        </p>
                      </article>
                    );
                  })}
                </details>
              ))}
            </div>
          ) : null}
          <div className="approval-actions">
            <ErrorNotice error={approval.error} />
            {draft ? (
              <Button
                disabled={busy || !lessons.length}
                onClick={async () => {
                  try {
                    await approval.mutateAsync(course.id);
                    navigate(`/courses/${course.id}/prepare`);
                  } catch {
                    /* Visible mutation feedback. */
                  }
                }}
              >
                {approval.isPending
                  ? "Saving your syllabus…"
                  : live
                    ? "Approve syllabus →"
                    : "Approve syllabus & create first lesson →"}
              </Button>
            ) : lessons[0] ? (
              <LinkButton to={`/courses/${course.id}/lessons/${lessons[0].id}`}>
                View first lesson →
              </LinkButton>
            ) : null}
            <p className="muted small">
              Your approval saves the plan. Video and quiz generation are not
              connected yet.
            </p>
          </div>
        </section>
        {app.guides ? (
          <GuidePanel
            api={app.guides}
            resourceId={course.id}
            guide="syllabus"
            generationMode={generationMode}
            disabled={busy}
            onBusyChange={setGuideBusy}
          />
        ) : (
          <aside className="guide-panel lavender syllabus-guide">
            <AgentThread
              entries={course.messages.map((item) => ({
                role: item.role === "guide" ? "assistant" : "user",
                text: item.text,
              }))}
              pendingMessage={
                generationPending ? generation.variables?.message : undefined
              }
              running={generationPending}
              disabled={busy}
              onSend={(text) =>
                generation.mutate({
                  courseId: course.id,
                  message: text,
                  expectedRevision: course.syllabus?.revision ?? 0,
                })
              }
            >
              <div className="guide-title">
                <Spark />
                <h2>Your course guide</h2>
              </div>
              <p className="muted small">
                {live
                  ? "Refine your syllabus through conversation. Your changes are saved."
                  : "Let’s make this feel right. · Demo"}
              </p>
              <div
                ref={conversation}
                className="conversation"
                role="log"
                aria-label="Syllabus changes"
                aria-live="polite"
              >
                <AgentMessages />
                {generationPending ? (
                  <>
                    <p role="status" className="message">
                      Your guide is reviewing your request. Research and
                      planning can take up to two minutes…
                    </p>
                  </>
                ) : null}
              </div>
              {draft && live ? (
                <ComposerPrimitive.Root
                  className="topic-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    try {
                      await generation.mutateAsync({
                        courseId: course.id,
                        message,
                        expectedRevision: course.syllabus?.revision ?? 0,
                      });
                      setMessage("");
                    } catch {
                      /* Retain the message and show the error for a deliberate retry. */
                    }
                  }}
                >
                  <QualitySettings
                    value={generationMode}
                    onChange={setGenerationMode}
                    disabled={busy}
                  />
                  <label htmlFor="guide-message">Ask your course guide</label>
                  <ComposerPrimitive.Input
                    submitMode="none"
                    id="guide-message"
                    rows={4}
                    maxLength={20000}
                    value={message}
                    disabled={busy}
                    onChange={(event) => setMessage(event.target.value)}
                    placeholder="e.g. Add a hands-on project and make week two less advanced"
                    required
                  />
                  <ErrorNotice error={generation.error} />
                  <Button type="submit" disabled={busy || !message.trim()}>
                    {generationPending
                      ? "Working on your syllabus…"
                      : !lessons.length
                        ? "Generate syllabus ↑"
                        : "Send request ↑"}
                  </Button>
                </ComposerPrimitive.Root>
              ) : null}
            </AgentThread>
            {draft && lessons.length ? (
              <details className="manual-topics" open={live ? undefined : true}>
                <summary>Edit a topic manually</summary>
                <form
                  className="topic-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    try {
                      await edit.mutateAsync({
                        courseId: course.id,
                        lessonId: selected,
                        topic,
                        operation: "add",
                      });
                      setTopic("");
                    } catch {
                      /* Visible mutation feedback. */
                    }
                  }}
                >
                  <label htmlFor="topic-lesson">Add a missing topic to</label>
                  <select
                    id="topic-lesson"
                    value={selected}
                    disabled={busy}
                    onChange={(event) => setSelectedLesson(event.target.value)}
                  >
                    {lessons.map((lesson) => (
                      <option key={lesson.id} value={lesson.id}>
                        {lesson.title}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="new-topic">
                    What would you like to cover?
                  </label>
                  <textarea
                    id="new-topic"
                    rows={3}
                    maxLength={200}
                    required
                    disabled={busy}
                    value={topic}
                    onChange={(event) => setTopic(event.target.value)}
                    placeholder="e.g. Debugging a program step by step"
                  />
                  <ErrorNotice error={edit.error} />
                  <Button type="submit" disabled={busy || !topic.trim()}>
                    {edit.isPending ? "Updating…" : "Add topic ↑"}
                  </Button>
                </form>
              </details>
            ) : null}
            {!draft ? (
              <p className="message">Your syllabus is approved and saved.</p>
            ) : null}
          </aside>
        )}
      </div>
    </>
  );
}
