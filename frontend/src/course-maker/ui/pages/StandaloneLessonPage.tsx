import { ElementPreparationToggle } from "../ElementPreparationToggle";
import { useRecordOpened } from "../use-learning-activity";
import { CancelGenerationButton } from "../CancelGenerationButton";
import { useEffect, useRef, useState } from "react";
import { CopyLessonButton } from "../CopyLessonButton";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import type { AnimatorModelChoice } from "../../application/animator-model";
import type { LessonPlanResponse } from "../../application/dto";
import type { GenerationMode } from "../../application/generation-mode";
import type {
  SaveOutlineRequest,
  StandaloneLessonResponse,
} from "../../application/standalone-lessons";
import { AnimatorModelSelector } from "../AnimatorModelSelector";
import {
  AgentComposer,
  AgentMessages,
  AgentThread,
} from "../assistant/AgentThread";
import { useApplication } from "../application-context";
import {
  ErrorNotice,
  LinkButton,
  PageHeading,
  QueryStatus,
  QueryWorkspace,
} from "../components";
import { CreatorLink } from "../CreatorLink";
import { QualitySettings } from "../GenerationModeSelector";
import {
  RegenerateMenu,
  rebuildSummary,
  type RegenerationStart,
} from "../RegenerateMenu";
import { useGenerationMode } from "../generation-mode";
import { GuidePanel } from "../GuidePanel";
import { useLessonMutation, useStandaloneLesson } from "../lesson-context";
import { LessonOutlineEditor } from "../LessonOutlineEditor";
import { LessonOutlineSummary } from "../LessonOutlineSummary";
import { LessonTimeFix } from "../LessonTimeFix";
import { LessonPipelineProgress } from "../LessonPipelineProgress";
import { LessonQuizPanel, LessonQuizPreview } from "../LessonQuiz";
import { useAutoQuiz } from "../lesson-quiz-context";
import { LessonScript } from "../LessonScript";
import { LessonSteps } from "../LessonSteps";
import {
  hasWatchableDraft,
  lessonWorkflowStatus,
  lessonWorkflowTone,
  type LessonRebuild,
} from "../lesson-workflow";
import { LessonInteractive } from "../learning/LessonInteractive";
import {
  InteractivesWhileYouWait,
  LessonInteractivesPanel,
} from "../interactives/InteractiveList";
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
  interactivePath,
  standaloneInteractiveHome,
} from "../interactives/interactive-paths";
import { useLessonInteractives } from "../lesson-interactive-context";
import { useLessonQuiz } from "../lesson-quiz-context";
import { LessonPlayer } from "../learning/LessonPlayer";
import {
  hasFinishedVideo,
  hasLessonArtifacts,
  lessonPlaybackUrl,
} from "../learning/lesson-view";
import { Button } from "../primitives/Button";
import { StylePanel } from "../StylePanel";
import { ThumbnailPanel } from "../ThumbnailPanel";

type Panel =
  "outline" | "script" | "voice" | "visuals" | "quiz" | "interactives";

const panelHints: Record<Panel, string> = {
  outline:
    "The teaching plan: what each part of the video covers. Edit it yourself or ask your lesson guide.",
  script:
    "The exact words your narrator will say. Reviewing it is optional — it’s written for you otherwise.",
  voice: "Who narrates your lesson and how they sound.",
  visuals: "The look and motion of your video.",
  quiz: "Multiple-choice questions learners answer after the video. Drafted from your outline — edit, add or remove any of them.",
  interactives:
    "Things learners can play with to make the lesson stick. Add as many as you like, whenever you like.",
};

export function StandaloneLessonPage() {
  const { lessonId = "" } = useParams();
  const query = useStandaloneLesson(lessonId);
  useRecordOpened(query.data?.id);
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  return (
    <QueryWorkspace error={query.error} retry={() => void query.refetch()}>
      <LessonWorkspace key={lessonId} lesson={query.data} />
    </QueryWorkspace>
  );
}

function LessonWorkspace({ lesson }: { lesson: StandaloneLessonResponse }) {
  const { lessons: app, guides, quizzes, interactives } = useApplication();
  const location = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [generationMode, setGenerationMode] = useGenerationMode(
    "lesson:" + lesson.id,
    undefined,
    (location.state as { generationMode?: GenerationMode } | null)
      ?.generationMode,
  );
  const [animatorModel, setAnimatorModel] = useState<AnimatorModelChoice>("");
  const [prepareElements, setPrepareElements] = useState(
    lesson.content.animation?.prepareElements ?? false,
  );
  const [guideBusy, setGuideBusy] = useState(false);
  const [guideDirty, setGuideDirty] = useState(false);
  const [styleBusy, setStyleBusy] = useState(false);
  const [styleDirty, setStyleDirty] = useState(false);
  const [scriptDirty, setScriptDirty] = useState(false);
  const [quizDirty, setQuizDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [sentMessage, setSentMessage] = useState<string>();
  const [editing, setEditing] = useState<{
    plan: LessonPlanResponse;
    revision: number;
  } | null>(null);
  const [outlineSaved, setOutlineSaved] = useState(false);
  const [rebuildBase, setRebuildBase] =
    useState<StandaloneLessonResponse["content"]>();
  const started = useRef(false);
  const arrival = location.state as {
    startPlanning?: boolean;
  } | null;
  // Only a create arrival starts work; saved activity restores the progress view.
  const [autoRun, setAutoRun] = useState(
    () => !!arrival?.startPlanning && lesson.flow === "automatic",
  );
  const [reviewAutomatic, setReviewAutomatic] = useState(false);
  const plan = lesson.content.plan;
  const scopeBlocked = plan?.feasibilityStatus === "infeasible";
  const ready = hasFinishedVideo(lesson.content);
  const playable = hasLessonArtifacts(lesson.content);
  const previous = lesson.playbackContent;
  const hasPlayback = playable || !!previous;
  const watchPrevious =
    params.get("watch") === "current" &&
    !!previous &&
    !(
      editing ||
      scriptDirty ||
      quizDirty ||
      styleDirty ||
      guideDirty ||
      message.trim()
    );
  const planning = useLessonMutation(async (text: string) => {
    if (!app)
      throw new Error("Lesson generation requires a server connection.");
    return app.plan.execute({
      id: lesson.id,
      expectedRevision: lesson.revision,
      message: text,
      generationMode,
    });
  });
  // Either a longer lesson or a narrower topic ends in a freshly planned outline.
  const fixingTime = useLessonMutation(
    async (fix: { minutes?: number; message: string }) => {
      if (!app)
        throw new Error("Lesson generation requires a server connection.");
      let current = lesson;
      if (fix.minutes) {
        if (!app.update) throw new Error("Draft updates are unavailable.");
        current = await app.update.execute({
          id: lesson.id,
          expectedRevision: lesson.revision,
          title: lesson.content.title,
          description: lesson.description,
          minutes: fix.minutes,
          generationMode,
        });
      }
      return app.plan.execute({
        id: lesson.id,
        expectedRevision: current.revision,
        message: fix.message,
        generationMode,
      });
    },
  );
  const savingOutline = useLessonMutation(
    async (outline: SaveOutlineRequest["outline"]) => {
      if (!app?.saveOutline || !editing)
        throw new Error("Outline editing is unavailable.");
      const result = await app.saveOutline.execute({
        id: lesson.id,
        expectedRevision: editing.revision,
        outline,
      });
      setEditing(null);
      setOutlineSaved(true);
      return result;
    },
  );
  const prepareScript = useLessonMutation<boolean | void>(
    async (regenerate) => {
      if (!app?.prepareScript) throw new Error("Script review is unavailable.");
      return app.prepareScript.execute({
        id: lesson.id,
        expectedRevision: lesson.revision,
        generationMode,
        ...(regenerate ? { regenerateFrom: "script" as const } : {}),
      });
    },
  );
  const generation = useLessonMutation<RegenerationStart | void>(
    async (restart) => {
      if (!app)
        throw new Error("Video generation requires a server connection.");
      return app.advance.execute({
        id: lesson.id,
        expectedRevision: lesson.revision,
        stage: restart === "outline" ? "automatic" : "video",
        ...(restart && restart !== "outline"
          ? { regenerateFrom: restart }
          : {}),
        ...(restart === "outline" ? { message: lesson.description } : {}),
        generationMode,
        ...(animatorModel ? { animatorModel } : {}),
        ...(prepareElements ? { prepareElements } : {}),
        animationBackend: "direct",
      });
    },
  );
  const automaticGeneration = useLessonMutation<void>(async () => {
    if (!app)
      throw new Error("Lesson generation requires a server connection.");
    return app.advance.execute({
      id: lesson.id,
      expectedRevision: lesson.revision,
      stage: "automatic",
      message: lesson.description,
      generationMode,
      ...(animatorModel ? { animatorModel } : {}),
      ...(prepareElements ? { prepareElements } : {}),
      animationBackend: "direct",
    });
  });
  const planningPending =
    planning.isPending ||
    fixingTime.isPending ||
    !!lesson.activeOperation?.endsWith("plan");
  const scriptPending =
    prepareScript.isPending ||
    /storyboard|script\/generate/.test(lesson.activeOperation ?? "");
  const videoPending =
    generation.isPending ||
    automaticGeneration.isPending ||
    /automatic|video|speech|animation/.test(lesson.activeOperation ?? "");
  const rebuild: LessonRebuild | undefined =
    generation.isPending && generation.variables && rebuildBase
      ? { from: generation.variables, before: rebuildBase }
      : undefined;
  // Until the new draft can play, the run is all there is to show: never the video it replaces.
  const building = videoPending && !hasWatchableDraft(lesson, rebuild);
  const busy =
    !!lesson.activeOperation ||
    planning.isPending ||
    fixingTime.isPending ||
    generation.isPending ||
    automaticGeneration.isPending ||
    prepareScript.isPending ||
    guideBusy ||
    styleBusy ||
    savingOutline.isPending;
  const dirty =
    styleDirty ||
    scriptDirty ||
    quizDirty ||
    guideDirty ||
    !!editing ||
    !!message.trim();
  const defaultStep =
    ready ||
    videoPending ||
    lesson.content.animation ||
    lesson.content.alignment ||
    (lesson.approved && lesson.operationError)
      ? "video"
      : "review";
  const requestedStep =
    params.get("step") === "review"
      ? "review"
      : params.get("step") === "video"
        ? "video"
        : defaultStep;
  const panelParam = params.get("panel");
  const requestedPanel: Panel =
    panelParam === "script" ||
    panelParam === "voice" ||
    panelParam === "visuals" ||
    (panelParam === "quiz" && !!quizzes) ||
    (panelParam === "interactives" && !!interactives)
      ? panelParam
      : "outline";
  const lastCleanView = useRef<{ step: "review" | "video"; panel: Panel }>({
    step: requestedStep,
    panel: requestedPanel,
  });
  useEffect(() => {
    if (!dirty)
      lastCleanView.current = { step: requestedStep, panel: requestedPanel };
  }, [dirty, requestedStep, requestedPanel]);
  // Keep the editor in the same subtree while browser history changes the URL.
  const step = dirty ? lastCleanView.current.step : requestedStep;
  const studio =
    (!!editing ||
      guideDirty ||
      scriptDirty ||
      quizDirty ||
      styleDirty ||
      params.get("edit") === "1" ||
      !playable ||
      step === "review") &&
    !watchPrevious;
  const panel: Panel =
    editing || guideDirty || message.trim()
      ? "outline"
      : scriptDirty
        ? "script"
        : quizDirty
          ? "quiz"
          : styleDirty
            ? lastCleanView.current.panel
            : requestedPanel;
  const setView = (
    nextStep: "review" | "video",
    edit = true,
    nextPanel: Panel = panel,
  ) => {
    setParams((previousParams) => {
      const next = new URLSearchParams(previousParams);
      next.set("step", nextStep);
      next.set("panel", nextPanel);
      if (edit) next.set("edit", "1");
      else next.delete("edit");
      next.delete("watch");
      next.delete("chat");
      next.delete("focus");
      next.delete("part");
      return next;
    });
  };
  useEffect(() => {
    if (
      (location.state as { startPlanning?: boolean } | null)?.startPlanning &&
      !started.current
    ) {
      started.current = true;
      navigate(location.pathname + location.search, {
        replace: true,
        state: null,
      });
      // An existing server operation already fulfils this arrival's request.
      if (lesson.activeOperation) return;
      if (lesson.flow === "automatic" && !scopeBlocked)
        automaticGeneration.mutate();
      else planning.mutate(lesson.description);
    }
  }, [
    location.state,
    location.pathname,
    location.search,
    lesson.activeOperation,
    plan,
    lesson.description,
    navigate,
    planning,
    automaticGeneration,
    lesson.flow,
    scopeBlocked,
  ]);
  useEffect(() => {
    if (
      autoRun &&
      (scopeBlocked ||
        (ready &&
          !busy &&
          !automaticGeneration.error &&
          !generation.error &&
          !lesson.operationError))
    )
      setAutoRun(false);
  }, [
    autoRun,
    scopeBlocked,
    ready,
    busy,
    automaticGeneration.error,
    generation.error,
    lesson.operationError,
  ]);
  const startVideo = (restart?: RegenerationStart) => {
    setRebuildBase(restart ? lesson.content : undefined);
    setView("video", false);
    generation.mutate(restart, { onSuccess: () => setView("video", false) });
  };
  const reviewScript = () => {
    setView("review", true, "script");
    if (!lesson.content.storyboard) prepareScript.mutate();
  };
  const watchCurrent = () =>
    setParams({ step: "video", ...(previous ? { watch: "current" } : {}) });
  // Draft the quiz once the video is ready, or when the creator opens its tab.
  useAutoQuiz(lesson, !!quizzes && (ready || panel === "quiz"));
  const playback = watchPrevious
    ? previous!
    : playable
      ? lesson.content
      : (previous ?? lesson.content);
  const editingVideo = studio && step === "video" && hasPlayback;
  const interactiveHome = standaloneInteractiveHome(lesson.id);
  const interactiveContext = {
    lessonId: lesson.id,
    title: lesson.content.title,
    topics: lesson.content.topics,
  };
  const allInteractives = useLessonInteractives(lesson.id).data ?? [];
  const inLesson = liveInteractives(allInteractives);
  const unfinished = allInteractives.length - inLesson.length;
  const quizQuestions = useLessonQuiz(lesson.id).data?.questions.length ?? 0;
  const showQuizPart = !studio && !!quizzes && ready && !watchPrevious;
  const parts: readonly LessonPart[] = [
    {
      id: "video",
      title: "Watch",
      detail: `${lesson.content.minutes} min video`,
    },
    ...interactiveParts(inLesson),
    ...(showQuizPart
      ? [
          {
            id: "quiz",
            title: "Quiz",
            detail: quizQuestions
              ? `${quizQuestions} question${quizQuestions === 1 ? "" : "s"}`
              : "Not set up yet",
          },
        ]
      : []),
  ];
  const { active: part, select: selectPart } = useLessonPart(parts);
  const viewing = studio ? "video" : part;
  const tried = useTriedPrompts();
  const mediaSurface = useRef<HTMLDivElement>(null);
  usePausedWhenHidden(mediaSurface, viewing !== "video");
  const player = (
    <>
      <LessonPlayer
        key={`${lesson.id}:${watchPrevious ? "previous" : "draft"}:${generation.data?.content.animation?.outputHash ?? ""}`}
        lesson={{ ...playback, videoUrl: lessonPlaybackUrl(playback) }}
        courseTitle="Lesson video"
      />
      <LessonInteractive interactive={playback.interactive} editing={studio} />
    </>
  );
  const videoStarted = !!(lesson.content.alignment || lesson.content.animation);
  const failed = !!(lesson.operationError || generation.error);
  // A finished video already reflects every saved change; it can still be rebuilt on request.
  const upToDate = ready && !failed;
  const pendingRebuild = rebuildSummary(lesson.content);
  const regenerateMenu = (primary: boolean) => (
    <RegenerateMenu
      primary={primary}
      disabled={!app || busy || dirty}
      options={[
        { start: "outline" },
        { start: "script", disabled: scopeBlocked },
        {
          start: "speech",
          disabled: scopeBlocked || !lesson.content.storyboard,
        },
        {
          start: "animation",
          disabled: scopeBlocked || !lesson.content.alignment,
        },
      ]}
      note={`Uses your ${generationMode[0].toUpperCase()}${generationMode.slice(1)} quality setting from Lesson settings.`}
      onSelect={startVideo}
    />
  );
  const generateButton = upToDate ? (
    regenerateMenu(true)
  ) : (
    <>
      {plan &&
        (hasPlayback || !!lesson.content.storyboard) &&
        !videoPending &&
        regenerateMenu(false)}
      <Button
        disabled={
          !app ||
          busy ||
          dirty ||
          scopeBlocked ||
          (!plan && panel === "outline")
        }
        onClick={
          plan ? () => startVideo() : () => setView("review", true, "outline")
        }
      >
        {!plan && panel !== "outline"
          ? "Review outline →"
          : videoPending
            ? "Creating video…"
            : failed
              ? "Retry video generation"
              : previous
                ? "Generate updated video →"
                : videoStarted
                  ? "Continue video generation →"
                  : "Create video →"}
      </Button>
    </>
  );
  const activity = planningPending
    ? {
        label: "Preparing your lesson outline",
        hint: "This usually takes about a minute.",
        cancel: "outline generation",
      }
    : scriptPending
      ? {
          label: "Writing your narration script",
          hint: "You can leave this page and come back to review it.",
          cancel: "script generation",
        }
      : videoPending
        ? {
            label: playable
              ? "Finishing your video in the background"
              : "Creating your video",
            hint: playable
              ? "You can already watch it. The final render continues."
              : "This can take a few minutes. You can leave this page — we’ll keep working.",
            cancel: "video generation",
          }
        : null;
  const cancelButton = activity && (
    <CancelGenerationButton
      kind="lesson"
      id={lesson.id}
      pending
      operation={lesson.activeOperation}
      label={activity.cancel}
    />
  );
  const header = (eyebrow: string) => (
    <>
      <Link className="back-link" to="/workspace">
        ← My creations <span>/ Lesson</span>
      </Link>
      <div className="heading-row lesson-workspace-heading">
        <PageHeading eyebrow={eyebrow} title={lesson.content.title} />
        <div className="workflow-inline-actions">
          <span
            className="workflow-status"
            role="status"
            data-tone={building ? "working" : lessonWorkflowTone(lesson)}
          >
            {building
              ? rebuild
                ? "Regenerating video"
                : "Creating video"
              : lessonWorkflowStatus(lesson)}
          </span>
          <CopyLessonButton
            lessonId={lesson.id}
            title={lesson.content.title}
            image={lesson.content.image}
            disabled={dirty}
          />
        </div>
      </div>
    </>
  );
  const guidance =
    guideDirty || message.trim()
      ? "Send or clear your guide message to continue."
      : dirty
        ? "Save or cancel your edits to continue."
        : scopeBlocked
          ? "Fix the lesson timing above before creating your script or video."
          : !plan
            ? "Generate an outline first — your script and video are built from it."
            : videoPending
              ? "Your video is being created. Completed steps are saved."
              : failed
                ? "Something interrupted the video. Retrying reuses the steps already finished."
                : upToDate
                  ? "Your video is up to date. Edit any step to make a new version, or regenerate it from any step."
                  : previous
                    ? `You have saved changes that aren’t in your video yet.${pendingRebuild ? ` Generating rebuilds ${pendingRebuild} and keeps everything before it.` : ""}`
                    : panel === "outline" && !lesson.content.storyboard
                      ? "Happy with the outline? Create your video — or check the narration script first."
                      : "Happy with your lesson? Create your video.";
  const tabs = (
    <nav
      className="lesson-editor-tabs"
      aria-label="What would you like to change?"
    >
      {(
        [
          "outline",
          "script",
          "voice",
          "visuals",
          ...(quizzes ? (["quiz"] as const) : []),
          ...(interactives ? (["interactives"] as const) : []),
        ] as const
      ).map((item) => (
        <button
          key={item}
          type="button"
          aria-pressed={panel === item}
          // Interactives build on their own, so a running video never blocks them.
          disabled={
            dirty ||
            (busy && item !== "interactives" && panel !== "interactives")
          }
          onClick={() => setView(step, true, item)}
        >
          {item === "outline"
            ? "Outline"
            : item === "script"
              ? "Script"
              : item === "voice"
                ? "Voice"
                : item === "quiz"
                  ? "Quiz"
                  : item === "interactives"
                    ? "Interactives"
                    : "Visuals"}
        </button>
      ))}
    </nav>
  );
  const tabsWithHint = (
    <>
      {tabs}
      <p className="lesson-editor-hint muted small">{panelHints[panel]}</p>
    </>
  );
  const reviewContent =
    panel === "outline" ? (
      <section className="lesson-outline" aria-label="Lesson outline">
        <div className="workflow-section-heading">
          <div>
            <h2>
              {step === "review"
                ? "Review your lesson outline"
                : "Lesson outline"}
            </h2>
            <p className="muted small">
              {lesson.content.minutes} min
              {lesson.content.style?.audience
                ? ` · For ${lesson.content.style.audience}`
                : ""}
            </p>
          </div>
          {plan && !editing && (
            <div className="workflow-inline-actions">
              <Button
                variant="secondary"
                disabled={busy || dirty || !app}
                onClick={() => planning.mutate(lesson.description)}
              >
                Regenerate outline
              </Button>
              <Button
                variant="secondary"
                disabled={busy || dirty || !app?.saveOutline}
                onClick={() => {
                  setOutlineSaved(false);
                  savingOutline.reset();
                  setEditing({ plan, revision: lesson.revision });
                }}
              >
                Edit outline
              </Button>
            </div>
          )}
        </div>
        {editing ? (
          <LessonOutlineEditor
            plan={editing.plan}
            minutes={lesson.content.minutes}
            topics={lesson.content.topics}
            pending={savingOutline.isPending}
            error={savingOutline.error}
            onSave={(outline) => savingOutline.mutate(outline)}
            onCancel={() => {
              setEditing(null);
              savingOutline.reset();
            }}
          />
        ) : plan ? (
          <>
            {outlineSaved && (
              <p role="status">
                Outline saved. Your next video will use these edits.
              </p>
            )}
            <LessonOutlineSummary plan={plan} showFeasibility={false} />
          </>
        ) : (
          <div
            className="outline-placeholder"
            role={planningPending ? "status" : undefined}
          >
            <h3>
              {planningPending ? (
                <>
                  <span className="loading-spinner" aria-hidden="true" />
                  Preparing your lesson outline…
                </>
              ) : (
                "Let’s shape your lesson."
              )}
            </h3>
            <p className="muted">
              {planningPending
                ? "Research and outline generation are in progress. You can leave and return to this saved lesson."
                : "Your guide will research the topic and build a focused outline from your lesson details."}
            </p>
            {!planningPending && (
              <Button
                disabled={busy || !app}
                onClick={() => planning.mutate(lesson.description)}
              >
                {lesson.operationError || planning.error || fixingTime.error
                  ? "Retry lesson outline"
                  : "Generate lesson outline →"}
              </Button>
            )}
          </div>
        )}
        <ErrorNotice error={planning.error ?? fixingTime.error} />
      </section>
    ) : panel === "script" ? (
      lesson.content.storyboard ? (
        <>
          <LessonScript
            lesson={lesson}
            disabled={busy}
            onDirtyChange={setScriptDirty}
            actions={
              <Button
                variant="secondary"
                disabled={busy || dirty || scopeBlocked || !app?.prepareScript}
                onClick={() => prepareScript.mutate(true)}
              >
                {scriptPending ? "Rewriting script…" : "Regenerate script"}
              </Button>
            }
          />
          <ErrorNotice error={prepareScript.error} />
        </>
      ) : (
        <section className="script-empty">
          <h2>Review script & voice</h2>
          <p>
            This optional step prepares the narration text before you create the
            video.
          </p>
          <p className="muted small">
            Your outline is saved. Narration and animation will wait until you
            choose Create video.
          </p>
          <Button
            disabled={busy || scopeBlocked || !plan || !app?.prepareScript}
            onClick={reviewScript}
          >
            {scriptPending ? "Preparing script…" : "Prepare script for review"}
          </Button>
          {scriptPending && (
            <p role="status">
              Preparing your script. You can leave this page and return to
              review it.
            </p>
          )}
          <ErrorNotice error={prepareScript.error} />
        </section>
      )
    ) : panel === "quiz" ? (
      <LessonQuizPanel lesson={lesson} onDirtyChange={setQuizDirty} />
    ) : panel === "interactives" ? (
      <LessonInteractivesPanel
        lesson={interactiveContext}
        home={interactiveHome}
      />
    ) : (
      <StylePanel
        key={panel}
        id={lesson.id}
        kind="lesson"
        style={lesson.content.style}
        history={lesson.content.styleHistory}
        focus={panel}
        generationMode={generationMode}
        disabled={
          !!lesson.activeOperation ||
          planningPending ||
          videoPending ||
          !!editing ||
          scriptDirty
        }
        onBusyChange={setStyleBusy}
        onDirtyChange={setStyleDirty}
      />
    );

  const autoActive =
    !reviewAutomatic &&
    !scopeBlocked &&
    !hasWatchableDraft(lesson, rebuild) &&
    (automaticGeneration.isPending ||
      (autoRun && (generation.isPending || !playable)) ||
      (lesson.flow === "automatic" &&
        !!(
          lesson.activeOperation ||
          lesson.operationError ||
          automaticGeneration.error ||
          (autoRun && generation.error)
        )));
  if (autoActive) {
    const working =
      automaticGeneration.isPending ||
      generation.isPending ||
      !!lesson.activeOperation;
    const autoError = automaticGeneration.error ?? generation.error;
    const autoFailed = !working && !!(autoError || lesson.operationError);
    // A run that ended without an error or a video, such as a cancelled one, can be continued.
    const autoStopped = !working && !autoFailed;
    const retryAutomatic = () => {
      automaticGeneration.reset();
      generation.reset();
      setAutoRun(true);
      if (plan) generation.mutate();
      else automaticGeneration.mutate();
    };
    return (
      <div className="lesson-workflow">
        {header("AUTOMATIC LESSON")}
        <LessonSteps
          active="video"
          lessonId={lesson.id}
          disabled
          flow="automatic"
        />
        {autoFailed && lesson.operationError && (
          <p className="workflow-error" role="alert">
            {lesson.operationError}
          </p>
        )}
        <LessonPipelineProgress
          lesson={lesson}
          running={!autoFailed && !autoStopped}
          error={autoError}
          automatic
          rebuild={rebuild}
          actions={cancelButton}
        />
        <ErrorNotice error={autoError} />
        {interactives && (
          <InteractivesWhileYouWait
            lesson={interactiveContext}
            home={interactiveHome}
          />
        )}
        <div className="workflow-actionbar">
          <p className="workflow-guidance">
            {autoFailed || autoStopped
              ? "Your progress is saved. Continuing reuses the steps already finished."
              : "We’ll open your video as soon as it’s ready to watch."}
          </p>
          <div className="workflow-inline-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setAutoRun(false);
                setReviewAutomatic(true);
              }}
            >
              Review step by step instead
            </Button>
            {(autoFailed || autoStopped) && (
              <Button disabled={!app} onClick={retryAutomatic}>
                {autoFailed ? "Retry" : "Continue"}
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (building)
    return (
      <div className="lesson-workflow">
        {header("YOUR LESSON")}
        <LessonSteps
          active="video"
          flow={lesson.flow}
          lessonId={lesson.id}
          disabled
        />
        <LessonPipelineProgress
          lesson={lesson}
          running
          rebuild={rebuild}
          actions={cancelButton}
        />
        {interactives && (
          <InteractivesWhileYouWait
            lesson={interactiveContext}
            home={interactiveHome}
          />
        )}
      </div>
    );

  return (
    <div className="lesson-workflow" data-view={studio ? "studio" : "watch"}>
      {header(studio ? "YOUR LESSON STUDIO" : "YOUR LESSON")}
      <LessonSteps
        active={step}
        flow={lesson.flow}
        lessonId={lesson.id}
        disabled={busy || dirty}
      />
      {activity && (
        <div className="workflow-activity">
          <span className="loading-spinner" aria-hidden="true" />
          <p role="status">
            <strong>{activity.label}…</strong> <span>{activity.hint}</span>
          </p>
          {cancelButton}
        </div>
      )}
      {lesson.operationError && !lesson.activeOperation && (
        <p className="workflow-error" role="alert">
          {lesson.operationError}
        </p>
      )}
      {scopeBlocked && studio && plan && (
        <LessonTimeFix
          plan={plan}
          minutes={lesson.content.minutes}
          disabled={busy || dirty || !app}
          pending={fixingTime.isPending}
          error={fixingTime.error}
          onExtend={(minutes) => {
            fixingTime.mutate({ minutes, message: lesson.description });
          }}
          onTrim={() => {
            fixingTime.mutate({
              message: [
                `Narrow the scope so the whole lesson fits in ${lesson.content.minutes} minutes.`,
                plan.recommendedScopeAdjustment,
                "Keep the most essential ideas and drop the rest.",
              ]
                .filter(Boolean)
                .join(" "),
            });
          }}
          onAskGuide={() => setView("review", true, "outline")}
        />
      )}
      {previous && studio && (
        <div className="workflow-version-notice" role="status">
          <strong>Editing a new draft.</strong> Your current video stays
          available while you make changes and generate its replacement.
          {videoPending && (
            <Button variant="secondary" disabled={dirty} onClick={watchCurrent}>
              Watch current video
            </Button>
          )}
        </div>
      )}
      {!studio && (
        <LessonPath
          parts={parts}
          active={part}
          onSelect={selectPart}
          add={
            interactives
              ? unfinished
                ? {
                    to: interactiveHome.backTo,
                    label: "Interactives",
                    detail: `${unfinished} not in lesson yet`,
                  }
                : {
                    to: interactivePath(interactiveHome, "new"),
                    label: "Add an interactive",
                    detail: "Let learners try it",
                  }
              : undefined
          }
        />
      )}
      {(!studio || editingVideo) && (
        <div
          key="lesson-media"
          ref={mediaSurface}
          className="lesson-media-workspace"
          hidden={viewing !== "video"}
        >
          {!studio && (
            <div className="workflow-section-heading">
              <p className="muted small">
                {watchPrevious
                  ? "Current video · your updated draft is saved separately"
                  : ready
                    ? "Your lesson video is ready to watch."
                    : "Lesson video"}
              </p>
              <div className="workflow-inline-actions">
                <Button
                  variant="secondary"
                  onClick={() => setView("review", true, "script")}
                >
                  View script
                </Button>
                <Button onClick={() => setView("video", true, "outline")}>
                  {previous ? "Continue editing" : "Edit video"}
                </Button>
              </div>
            </div>
          )}
          <div
            className={studio ? "lesson-video-editor" : "lesson-video-watch"}
          >
            <div className="lesson-editor-player">{player}</div>
            {studio && (
              <div className="lesson-editor-inspector">
                {tabsWithHint}
                {reviewContent}
              </div>
            )}
          </div>
        </div>
      )}
      {step === "video" && videoPending && hasPlayback && (
        <LessonPipelineProgress lesson={lesson} running rebuild={rebuild} />
      )}
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
      {showQuizPart && part === "quiz" && (
        <LessonQuizPreview
          lesson={lesson}
          onEdit={() => setView("video", true, "quiz")}
        />
      )}
      {!studio && (
        <NextPart parts={parts} active={part} onSelect={selectPart} />
      )}
      {!studio ? (
        <CreatorLink id={lesson.ownerId} />
      ) : step === "video" && !editingVideo ? (
        <>
          <LessonPipelineProgress
            lesson={lesson}
            running={videoPending}
            error={generation.error}
          />
          <ErrorNotice error={generation.error} />
          <div className="workflow-actionbar">
            <Button
              variant="secondary"
              disabled={dirty}
              onClick={() => setView("review", true, "outline")}
            >
              Back to review
            </Button>
            <div className="workflow-inline-actions">{generateButton}</div>
          </div>
        </>
      ) : (
        <>
          {editingVideo ? null : (
            <>
              {tabsWithHint}
              <div
                className={`lesson-review-workspace ${panel !== "outline" ? "focused-review" : ""}`}
              >
                <div className="workflow-surface">{reviewContent}</div>
                {panel === "outline" && (
                  <div className="lesson-review-guide">
                    {guides ? (
                      <GuidePanel
                        api={guides}
                        resourceId={lesson.id}
                        guide="lesson"
                        generationMode={generationMode}
                        disabled={
                          busy || styleDirty || scriptDirty || !!editing
                        }
                        onBusyChange={setGuideBusy}
                        onDirtyChange={setGuideDirty}
                      />
                    ) : (
                      <aside className="lesson-chat panel">
                        <h2>Your lesson guide</h2>
                        <p className="muted small">
                          Ask AI to revise this outline.
                        </p>
                        <AgentThread
                          turns={lesson.turns}
                          pendingMessage={sentMessage}
                          running={planningPending}
                          disabled={busy || !!editing}
                          onSend={(text) => {
                            setSentMessage(text);
                            setMessage("");
                            planning.mutate(text, {
                              onError: () => setMessage(text),
                              onSettled: () => setSentMessage(undefined),
                            });
                          }}
                        >
                          <div
                            className="lesson-chat-messages"
                            role="log"
                            aria-label="Lesson conversation"
                          >
                            <AgentMessages />
                            {planningPending && (
                              <p
                                role="status"
                                aria-label="Lesson guide is thinking"
                              >
                                Updating your outline…
                                <span
                                  className="thinking-dots"
                                  aria-hidden="true"
                                >
                                  <span />
                                  <span />
                                  <span />
                                </span>
                              </p>
                            )}
                          </div>
                          <AgentComposer
                            label="Message your lesson guide"
                            value={message}
                            onChange={setMessage}
                            disabled={busy || !!editing}
                            sendDisabled={!plan || lesson.turns.length >= 50}
                            onSend={() => {
                              const text = message.trim();
                              if (!text || !plan) return;
                              setSentMessage(text);
                              setMessage("");
                              planning.mutate(text, {
                                onError: () => setMessage(text),
                                onSettled: () => setSentMessage(undefined),
                              });
                            }}
                          >
                            <p className="muted small">
                              Requested changes revise the outline. Your current
                              video remains available.
                            </p>
                          </AgentComposer>
                        </AgentThread>
                      </aside>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
          <div className="workflow-actionbar">
            <div>
              <p className="workflow-guidance">{guidance}</p>
              {styleDirty && (
                <p role="status" className="muted small">
                  Save or cancel your style changes before generating.
                </p>
              )}
            </div>
            <div className="workflow-inline-actions">
              {hasPlayback && (
                <Button
                  variant="secondary"
                  disabled={dirty}
                  onClick={watchCurrent}
                >
                  {previous ? "Watch current video" : "Done editing"}
                </Button>
              )}
              {!ready && !previous && panel === "outline" && (
                <Button
                  variant="secondary"
                  disabled={
                    busy ||
                    dirty ||
                    scopeBlocked ||
                    !plan ||
                    !app?.prepareScript
                  }
                  onClick={reviewScript}
                >
                  Review script first
                </Button>
              )}
              {generateButton}
            </div>
          </div>
        </>
      )}
      <section className="lesson-extras" aria-labelledby="lesson-extras-title">
        <h2 id="lesson-extras-title">Lesson settings</h2>
        {studio && (
          <QualitySettings
            value={generationMode}
            onChange={setGenerationMode}
            disabled={busy || dirty}
          >
            <AnimatorModelSelector
              value={animatorModel}
              onChange={setAnimatorModel}
              mode={generationMode}
              disabled={busy || dirty}
            />
            <ElementPreparationToggle
              checked={prepareElements}
              onChange={setPrepareElements}
              disabled={busy || dirty}
            />
          </QualitySettings>
        )}
        <details className="settings-disclosure">
          <summary>
            Thumbnail
            <span className="summary-value">
              {lesson.content.image ? "Added" : "Not yet"}
            </span>
          </summary>
          <ThumbnailPanel
            id={lesson.id}
            kind="lesson"
            image={lesson.content.image}
            preparing={!!lesson.thumbnailOperation && !lesson.content.image}
            disabled={dirty}
          />
        </details>
      </section>
    </div>
  );
}
