import { useRecordOpened } from "../use-learning-activity";
import { QueryWorkspace } from "../components";
import { ActivityNotice } from "../activity";
import { ThumbnailPanel } from "../ThumbnailPanel";
import { useState } from "react";
import { StyleFields } from "../StyleFields";
import { styleInputFromResponse } from "../../application/style";
import {
  Link,
  useNavigate,
  useSearchParams,
  useParams,
} from "react-router-dom";
import { useApplication } from "../application-context";
import { useLessonMutation, useStandaloneLesson } from "../lesson-context";
import type {
  CreateLessonRequest,
  StandaloneLessonResponse,
} from "../../application/standalone-lessons";
import { ErrorNotice, PageHeading, Spark, QueryStatus } from "../components";
import { GenerationModeSelector } from "../GenerationModeSelector";
import { useGenerationMode } from "../generation-mode";
import { Button } from "../primitives/Button";
import { LessonSteps } from "../LessonSteps";
import { LessonFlowSelector } from "../LessonFlowSelector";
import type { LessonFlow } from "../../application/lesson-flow";
import { InteractiveIdeasField } from "../interactives/InteractiveIdeasField";
import { useInteractiveMutation } from "../lesson-interactive-context";

export function CreateLessonPage() {
  const { lessonId = "" } = useParams();
  const query = useStandaloneLesson(lessonId);
  useRecordOpened(query.data?.id);
  if (lessonId && !query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  return (
    <QueryWorkspace
      error={query.error}
      retry={() => {
        void query.refetch();
      }}
    >
      <LessonDetailsForm key={lessonId} initial={query.data} />
    </QueryWorkspace>
  );
}

const sectionId = (name: string) => "lesson-form-" + name;

function LessonDetailsForm({
  initial,
}: {
  initial?: StandaloneLessonResponse;
}) {
  const { lessons: app, interactives } = useApplication();
  const navigate = useNavigate();
  const [ideas, setIdeas] = useState<readonly string[]>([]);
  const [ideaText, setIdeaText] = useState("");
  const [generationMode, setGenerationMode, rememberGenerationMode] =
    useGenerationMode(
      initial ? "lesson:" + initial.id : "new-lesson",
      undefined,
      undefined,
      undefined,
      "fast",
    );
  const [flow, setFlow] = useState<LessonFlow>(initial?.flow ?? "automatic");
  const automatic = flow === "automatic";
  const [params] = useSearchParams();
  const [minutes, setMinutes] = useState(initial?.content.minutes ?? 3);
  const [title, setTitle] = useState(
    initial?.content.title ?? params.get("title") ?? "",
  );
  const [description, setDescription] = useState(
    initial?.description ?? params.get("description") ?? "",
  );
  const [style, setStyle] = useState(() =>
    styleInputFromResponse(initial?.content.style),
  );
  const [savedDraft, setDraft] = useState(initial);
  const draft =
    initial && (!savedDraft || initial.revision >= savedDraft.revision)
      ? initial
      : savedDraft;
  const [saved, setSaved] = useState(
    initial
      ? JSON.stringify({
          title: initial.content.title,
          description: initial.description,
          minutes: initial.content.minutes,
          style: styleInputFromResponse(initial?.content.style),
          flow: initial.flow,
        })
      : "",
  );
  const details = { title, description, minutes, style, flow };
  const dirty = JSON.stringify(details) !== saved;
  const startIdea = useInteractiveMutation(
    (request: { lessonId: string; brief: string }) => {
      if (!interactives) throw new Error("Interactives are unavailable.");
      return interactives.create(request);
    },
  );
  const creation = useLessonMutation((request: CreateLessonRequest) => {
    if (!app) throw new Error("Connect to the server to create a lesson.");
    if (draft) {
      if (!app.update) throw new Error("Draft updates are unavailable.");
      return app.update.execute({
        ...request,
        id: draft.id,
        expectedRevision: draft.revision,
      });
    }
    return app.create.execute(request);
  });
  const busy =
    creation.isPending || startIdea.isPending || !!initial?.activeOperation;
  const save = async (stay: boolean) => {
    const lesson =
      !dirty && draft
        ? draft
        : await creation.mutateAsync({ ...details, generationMode });
    setDraft(lesson);
    setSaved(JSON.stringify(details));
    rememberGenerationMode("lesson:" + lesson.id, generationMode);
    // Each idea leaves the list once it is building, so a retry never repeats one.
    const typed = ideaText.trim();
    for (const brief of new Set(typed ? [...ideas, typed] : ideas)) {
      await startIdea.mutateAsync({ lessonId: lesson.id, brief });
      setIdeas((current) => current.filter((idea) => idea !== brief));
      if (brief === typed) setIdeaText("");
    }
    if (!draft && stay)
      navigate(`/lessons/${lesson.id}/edit`, { replace: true });
    return lesson;
  };
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
        eyebrow={initial ? "LESSON DETAILS" : "NEW LESSON"}
        title={initial ? "Update your lesson details" : "Let’s make a lesson."}
      >
        {initial
          ? automatic
            ? "Change the topic, audience, look, or length. We’ll rebuild the lesson and video for you."
            : "Change the topic, audience, look, or length. You’ll review the updated outline before any video is made."
          : automatic
            ? "Tell us what to teach and who it’s for. We’ll take it all the way to a finished video."
            : "Tell us what to teach and who it’s for. You’ll review an outline before anything is turned into video."}
      </PageHeading>
      <LessonSteps
        active="details"
        lessonId={initial?.id}
        disabled={dirty || busy}
        flow={flow}
      />
      {initial?.content.plan && (
        <p className="workflow-impact">
          Changing the lesson details creates a new outline and rebuilds
          downstream media. Your current video stays available until its
          replacement is ready.
        </p>
      )}
      <div className="creation-grid standalone-creation">
        <form
          className="panel course-form"
          aria-busy={busy}
          onSubmit={async (event) => {
            event.preventDefault();
            const saveOnly =
              (event.nativeEvent as SubmitEvent).submitter?.getAttribute(
                "value",
              ) === "draft";
            try {
              const lesson = await save(saveOnly);
              if (saveOnly) return;
              rememberGenerationMode("lesson:" + lesson.id, generationMode);
              navigate(`/lessons/${lesson.id}`, {
                state: { startPlanning: true, generationMode, flow },
              });
            } catch {
              /* Feedback below keeps the form intact. */
            }
          }}
        >
          <fieldset disabled={busy} className="creation-fields">
            <section
              className="form-section"
              aria-labelledby={sectionId("topic")}
            >
              <h2 id={sectionId("topic")}>
                <span aria-hidden="true">1</span>What’s your lesson about?
              </h2>
              <p className="muted small">
                Add a title or describe what you want to learn. We’ll infer the
                other field.
              </p>
              <label htmlFor="lesson-title">Lesson title</label>
              <input
                id="lesson-title"
                name="title"
                maxLength={120}
                placeholder="e.g. Why atoms form bonds"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                autoFocus
              />
              <label htmlFor="lesson-description">
                What would you like to learn?
              </label>
              <textarea
                id="lesson-description"
                name="description"
                maxLength={2000}
                rows={4}
                placeholder="Tell us what to cover and any examples you’d like to see…"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
              <label htmlFor="lesson-audience">Who is this for?</label>
              <input
                id="lesson-audience"
                maxLength={2000}
                value={style.audience}
                onChange={(event) =>
                  setStyle({ ...style, audience: event.target.value })
                }
                placeholder="Optional — e.g. beginners, children aged 8–10, or college students"
              />
            </section>
            <section
              className="form-section"
              aria-labelledby={sectionId("look")}
            >
              <h2 id={sectionId("look")}>
                <span aria-hidden="true">2</span>How should it look and sound?
              </h2>
              <StyleFields
                value={style}
                prominentAudience
                onChange={setStyle}
                disabled={busy}
              />
            </section>
            <section
              className="form-section"
              aria-labelledby={sectionId("length")}
            >
              <h2 id={sectionId("length")}>
                <span aria-hidden="true">3</span>How long should the video be?
              </h2>
              <fieldset className="lesson-duration">
                <legend className="sr-only">Lesson duration</legend>
                <div className="duration-heading">
                  <strong>
                    {minutes}{" "}
                    <span>{minutes === 1 ? "minute" : "minutes"}</span>
                  </strong>
                  <span className="pill sage">10 MIN MAX</span>
                </div>
                <label className="sr-only" htmlFor="lesson-minutes">
                  Duration in minutes
                </label>
                <input
                  id="lesson-minutes"
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={minutes}
                  onChange={(event) => setMinutes(Number(event.target.value))}
                  aria-valuetext={`${minutes} ${minutes === 1 ? "minute" : "minutes"}`}
                />
                <div className="duration-scale" aria-hidden="true">
                  <span>1 min</span>
                  <span>5 min</span>
                  <span>10 min</span>
                </div>
                <div
                  className="duration-presets"
                  aria-label="Quick duration choices"
                >
                  {[1, 3, 5, 10].map((value) => (
                    <button
                      key={value}
                      type="button"
                      className={value === minutes ? "selected" : ""}
                      aria-pressed={value === minutes}
                      onClick={() => setMinutes(value)}
                    >
                      {value} min
                    </button>
                  ))}
                </div>
              </fieldset>
            </section>
            <section
              className="form-section"
              aria-labelledby={sectionId("quality")}
            >
              <h2 id={sectionId("quality")}>
                <span aria-hidden="true">4</span>How much quality do you need?
              </h2>
              <GenerationModeSelector
                value={generationMode}
                onChange={setGenerationMode}
                disabled={busy}
                showLegend={false}
              />
            </section>
            <section
              className="form-section"
              aria-labelledby={sectionId("flow")}
            >
              <h2 id={sectionId("flow")}>
                <span aria-hidden="true">5</span>How do you want to make it?
              </h2>
              <LessonFlowSelector
                value={flow}
                onChange={setFlow}
                disabled={busy}
              />
            </section>
            {interactives && (
              <section
                className="form-section"
                aria-labelledby={sectionId("interactives")}
              >
                <h2 id={sectionId("interactives")}>
                  <span aria-hidden="true">6</span>Anything learners should try?
                </h2>
                <InteractiveIdeasField
                  ideas={ideas}
                  onChange={setIdeas}
                  text={ideaText}
                  onTextChange={setIdeaText}
                  disabled={busy}
                />
              </section>
            )}
            <ErrorNotice error={creation.error ?? startIdea.error} />
            <Button type="submit" disabled={busy || !app}>
              {busy
                ? "Saving your lesson…"
                : automatic
                  ? "Create my lesson →"
                  : "Build my lesson outline →"}
            </Button>
            <p className="muted small submit-hint">
              {automatic
                ? "Takes a few minutes. We’ll show you the finished video — you can edit anything afterwards."
                : "Takes about a minute. No video is made until you approve the outline."}
            </p>
            <div className="draft-save-bar">
              <Button
                type="submit"
                name="action"
                value="draft"
                variant="secondary"
                disabled={
                  busy || !app || (!dirty && !ideas.length && !ideaText.trim())
                }
              >
                Save as draft
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
        <aside className="guide-panel lavender lesson-guide">
          <Spark />
          <h2>From an idea to a video.</h2>
          <ol className="journey-steps">
            <li data-state="current">
              <strong>Describe your lesson</strong>
              <span>You’re here. Everything is saved as you go.</span>
            </li>
            {automatic ? (
              <>
                <li>
                  <strong>We build it for you</strong>
                  <span>
                    Outline, script, narration and animation run one after
                    another. No review stops.
                  </span>
                </li>
                <li>
                  <strong>Watch your video</strong>
                  <span>
                    When it’s ready it opens right away. Edit anything and
                    regenerate if you want changes.
                  </span>
                </li>
              </>
            ) : (
              <>
                <li>
                  <strong>Review the outline</strong>
                  <span>
                    About a minute. Edit it yourself or ask the lesson guide for
                    changes.
                  </span>
                </li>
                <li>
                  <strong>Create your video</strong>
                  <span>
                    A few minutes for narration and animation. Watch it, then
                    edit anything and regenerate.
                  </span>
                </li>
              </>
            )}
          </ol>
          <div className="lesson-time-mark" aria-hidden="true">
            <span>{String(minutes).padStart(2, "0")}</span>
            <small>Minutes of video, approximately</small>
          </div>
        </aside>
      </div>
      {draft && (
        <details className="settings-disclosure settings-card">
          <summary>
            Lesson thumbnail
            <span className="summary-value">Optional</span>
          </summary>
          <ThumbnailPanel
            disabled={dirty}
            id={draft.id}
            kind="lesson"
            image={draft.content.image}
            onSaved={(result) => {
              if ("content" in result) setDraft(result);
            }}
          />
        </details>
      )}
    </>
  );
}
