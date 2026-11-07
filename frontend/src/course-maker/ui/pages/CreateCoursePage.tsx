import { useRecordOpened } from "../use-learning-activity";
import { QueryWorkspace } from "../components";
import { ActivityNotice } from "../activity";
import { ThumbnailPanel } from "../ThumbnailPanel";
import { useState } from "react";
import { StyleFields } from "../StyleFields";
import { styleInputFromResponse } from "../../application/style";
import type {
  CourseResponse,
  CreateCourseRequest,
} from "../../application/dto";
import { schema, type FormValues } from "../forms/course-form-schema";
import { useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useParams } from "react-router-dom";
import { GenerationModeSelector } from "../GenerationModeSelector";
import { useGenerationMode } from "../generation-mode";
import { Button } from "../primitives/Button";
import {
  useApplication,
  useCourseMutation,
  useCourse,
} from "../application-context";
import { ErrorNotice, PageHeading, Spark, QueryStatus } from "../components";

// Keep both duration modes in the form draft so toggling never discards input.
const defaults = {
  mode: "weekly" as const,
  title: "",
  description: "",
  weeks: 4,
  hoursPerWeek: 3,
  hours: 3,
};

export function CreateCoursePage() {
  const { courseId = "" } = useParams();
  const query = useCourse(courseId);
  useRecordOpened(query.data?.id);
  if (courseId && !query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  if (query.data?.status === "ready")
    return (
      <p>
        This course is finished. <Link to="/workspace">Back to workspace</Link>
      </p>
    );
  if (query.data?.chapters.length)
    return (
      <p>
        Continue refining this syllabus in the{" "}
        <Link to={`/courses/${courseId}/syllabus`}>course studio</Link>.
      </p>
    );
  return (
    <QueryWorkspace
      error={query.error}
      retry={() => {
        void query.refetch();
      }}
    >
      <CourseDetailsForm key={courseId} initial={query.data} />
    </QueryWorkspace>
  );
}

function CourseDetailsForm({ initial }: { initial?: CourseResponse }) {
  const app = useApplication();
  const navigate = useNavigate();
  const [generationMode, setGenerationMode, rememberGenerationMode] =
    useGenerationMode(initial ? "course:" + initial.id : "new-course");
  const build = useCourseMutation(
    (request: {
      courseId: string;
      message: string;
      expectedRevision: number;
    }) => {
      if (!app.buildCourseDraft) throw new Error("Course builder unavailable");
      return app.buildCourseDraft.execute({ ...request, generationMode });
    },
  );
  const [style, setStyle] = useState(() =>
    styleInputFromResponse(initial?.style),
  );
  const [savedDraft, setDraft] = useState(initial);
  const draft = initial ?? savedDraft;
  const [saved, setSaved] = useState(
    initial
      ? JSON.stringify({
          title: initial.title,
          description: initial.description,
          duration: initial.duration,
          style: styleInputFromResponse(initial?.style),
        })
      : "",
  );
  const mutation = useCourseMutation((request: CreateCourseRequest) =>
    app.saveCourseDraft
      ? app.saveCourseDraft.execute({ ...request, id: draft?.id })
      : app.createCourse.execute(request),
  );
  const {
    register,
    watch,
    setValue,
    handleSubmit,
    getFieldState,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: initial
      ? {
          ...defaults,
          title: initial.title,
          description: initial.description,
          ...initial.duration,
        }
      : defaults,
  });
  const busy =
    !!initial?.activeOperation || mutation.isPending || build.isPending;
  const values = watch();
  const request = (data: FormValues): CreateCourseRequest => ({
    title: data.title,
    description: data.description,
    duration:
      data.mode === "total"
        ? { mode: "total", hours: data.hours }
        : {
            mode: "weekly",
            weeks: data.weeks,
            hoursPerWeek: data.hoursPerWeek,
          },
    style,
  });
  const dirty = JSON.stringify(request(values)) !== saved;
  const save = async (data: FormValues, stay = true) => {
    const details = request(data);
    const course =
      !dirty && draft
        ? draft
        : await mutation.mutateAsync({ ...details, generationMode });
    setDraft(course);
    setSaved(JSON.stringify(details));
    rememberGenerationMode("course:" + course.id, generationMode);
    if (!draft && stay)
      navigate(`/courses/${course.id}/edit`, { replace: true });
    return course;
  };
  const total =
    values.mode === "total" ? values.hours : values.weeks * values.hoursPerWeek;
  const fieldError = (key: FieldPath<FormValues>) => {
    const error = getFieldState(key).error;
    return error ? (
      <span id={key + "-error"} className="field-error" role="alert">
        {error.message}
      </span>
    ) : null;
  };
  const attributes = (key: FieldPath<FormValues>) => ({
    "aria-invalid": key in errors,
    "aria-describedby": key in errors ? key + "-error" : undefined,
  });
  return (
    <>
      <Link className="back-link" to={initial ? "/workspace" : "/"}>
        {initial ? "← My creations" : "← My learning"}
      </Link>
      <ActivityNotice
        operation={initial?.activeOperation}
        error={initial?.operationError}
      />
      <PageHeading
        eyebrow="01  COURSE DETAILS    /    02  YOUR SYLLABUS"
        title="Let’s make room for something new."
      >
        Tell your guide what you want to learn. You’ll shape the plan together.
      </PageHeading>
      {draft && (
        <ThumbnailPanel
          disabled={dirty}
          id={draft.id}
          kind="course"
          image={draft.image}
          onSaved={(result) => {
            if ("chapters" in result) setDraft(result);
          }}
        />
      )}
      <div className="creation-grid">
        <form
          className="panel course-form"
          noValidate
          aria-busy={busy}
          onSubmit={handleSubmit(async (data) => {
            try {
              let course = await save(data, false);
              if (app.buildCourseDraft && !course.chapters.length)
                course = await build.mutateAsync({
                  courseId: course.id,
                  message: data.description,
                  expectedRevision: 0,
                });
              rememberGenerationMode("course:" + course.id, generationMode);
              navigate("/courses/" + course.id + "/syllabus", {
                state: {
                  initialMessage: course.chapters.length
                    ? undefined
                    : data.description,
                  generationMode,
                },
              });
            } catch {
              /* Mutation feedback is rendered below. */
            }
          })}
        >
          <fieldset disabled={busy} className="creation-fields">
            <section
              className="form-section"
              aria-labelledby="course-form-topic"
            >
              <h2 id="course-form-topic">
                <span aria-hidden="true">1</span>What do you want to learn?
              </h2>
              <label htmlFor="title">Course title</label>
              <input
                id="title"
                placeholder="e.g. Python for everyday life"
                maxLength={120}
                autoFocus
                {...register("title")}
                {...attributes("title")}
              />
              {fieldError("title")}
              <label htmlFor="description">What would you like to learn?</label>
              <textarea
                id="description"
                rows={4}
                maxLength={2000}
                placeholder="I’m a beginner. I’d like to learn the basics, work with files, and build something useful…"
                {...register("description")}
                {...attributes("description")}
              />
              {fieldError("description")}
            </section>
            <section
              className="form-section"
              aria-labelledby="course-form-look"
            >
              <h2 id="course-form-look">
                <span aria-hidden="true">2</span>How should it look and sound?
              </h2>
              <StyleFields
                value={style}
                onChange={setStyle}
                label="Course style"
                disabled={busy}
              />
            </section>
            <section
              className="form-section"
              aria-labelledby="course-form-time"
            >
              <h2 id="course-form-time">
                <span aria-hidden="true">3</span>How much time do you have?
              </h2>
              <fieldset>
                <legend className="sr-only">
                  How much time would you like to spend?
                </legend>
                <div className="segmented">
                  <label>
                    <input
                      type="radio"
                      value="total"
                      {...register("mode")}
                      onChange={() => {
                        setValue("mode", "total");
                      }}
                    />
                    <span>Total hours</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      value="weekly"
                      {...register("mode")}
                      onChange={() => {
                        setValue("mode", "weekly");
                      }}
                    />
                    <span>Weekly schedule</span>
                  </label>
                </div>
              </fieldset>
              {values.mode === "total" ? (
                <div>
                  <label htmlFor="hours">Total learning hours</label>
                  <input
                    id="hours"
                    type="number"
                    min="1"
                    max="480"
                    step="0.5"
                    {...register("hours", { valueAsNumber: true })}
                    {...attributes("hours")}
                  />
                  {fieldError("hours")}
                </div>
              ) : (
                <div className="field-pair">
                  <div>
                    <label htmlFor="weeks">Course duration (weeks)</label>
                    <input
                      id="weeks"
                      type="number"
                      min="1"
                      max="12"
                      {...register("weeks", { valueAsNumber: true })}
                      {...attributes("weeks")}
                    />
                    {fieldError("weeks")}
                  </div>
                  <div>
                    <label htmlFor="hoursPerWeek">Hours per week</label>
                    <input
                      id="hoursPerWeek"
                      type="number"
                      min="1"
                      max="40"
                      step="0.5"
                      {...register("hoursPerWeek", { valueAsNumber: true })}
                      {...attributes("hoursPerWeek")}
                    />
                    {fieldError("hoursPerWeek")}
                  </div>
                </div>
              )}
              <div className="time-summary sage" aria-live="polite">
                <strong>
                  {Number.isFinite(total) ? total : "—"} hours of learning
                  {values.mode === "weekly"
                    ? " over " + values.weeks + " weeks"
                    : ""}
                </strong>
                <p>Includes videos, quizzes, and practice time.</p>
              </div>
              <p className="muted small">
                Up to 3 months (12 weeks) · 8 hours a day, 5 days a week,
                maximum.
                <br />
                For a short course, choose Total hours — for example, 2 or 3
                hours.
              </p>
            </section>
            <section
              className="form-section"
              aria-labelledby="course-form-quality"
            >
              <h2 id="course-form-quality">
                <span aria-hidden="true">4</span>Quality &amp; speed
              </h2>
              <GenerationModeSelector
                value={generationMode}
                onChange={setGenerationMode}
                disabled={busy}
                showLegend={false}
              />
            </section>
            <ErrorNotice error={mutation.error || build.error} />
            {mutation.isPending ? (
              <p role="status" className="muted small">
                Saving your course details…
              </p>
            ) : null}
            <Button type="submit" disabled={busy}>
              {mutation.isPending
                ? "Saving your course…"
                : "Build my syllabus →"}
            </Button>
            <p className="muted small submit-hint">
              You can refine the plan before any lessons are generated.
            </p>
            <div className="draft-save-bar">
              <Button
                type="button"
                variant="secondary"
                disabled={busy || !dirty}
                onClick={() =>
                  void handleSubmit(async (data) => {
                    try {
                      await save(data);
                    } catch {
                      /* Keep edits for retry. */
                    }
                  })()
                }
              >
                {mutation.isPending ? "Saving…" : "Save as draft"}
              </Button>
              <span role="status" className="muted small">
                {saved
                  ? dirty
                    ? "Unsaved changes"
                    : "Draft saved · Find it in My creations"
                  : "Not ready yet? Save a draft and finish it later."}
              </span>
            </div>
          </fieldset>
        </form>
        <aside className="guide-panel lavender">
          <Spark />
          <h2>
            Your idea.
            <br />A little guidance.
          </h2>
          <p>
            Start with the essentials. Your guide will turn them into chapters
            and lessons that build on each other.
          </p>
          <ol className="journey-steps">
            <li data-state="current">
              <strong>Share your course idea</strong>
              <span>You’re here. Save a draft anytime.</span>
            </li>
            <li>
              <strong>Review and refine the syllabus</strong>
              <span>
                Your guide drafts chapters and lessons. Refine them in chat or
                edit topics yourself.
              </span>
            </li>
            <li>
              <strong>Approve and save your course plan</strong>
              <span>Then open any lesson to create its video.</span>
            </li>
          </ol>
          <p className="muted small">
            {app.generateSyllabus
              ? "Your guide can research current sources and remember your changes as you refine the course."
              : "Demo mode uses a sample outline, not a live AI model."}
          </p>
        </aside>
      </div>
    </>
  );
}
