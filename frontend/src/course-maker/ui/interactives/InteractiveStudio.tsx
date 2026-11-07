import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  briefProblem,
  changeProblem,
  detailsProblem,
  interactiveBuildStages,
  interactiveIdeas,
  interactiveLimits,
  interactiveState,
  type InteractiveBuildStage,
  type InteractiveLessonContext,
  type LessonInteractive,
} from "../../application/lesson-interactives";
import { useApplication } from "../application-context";
import { ErrorNotice, QueryStatus } from "../components";
import {
  useInteractiveMutation,
  useLessonInteractive,
  useRemoveInteractive,
} from "../lesson-interactive-context";
import { Button } from "../primitives/Button";
import { InteractiveStage } from "./InteractiveStage";
import { InteractiveStatus } from "./InteractiveStatus";
import { interactivePath, type InteractiveHome } from "./interactive-paths";

const stageLabels: Record<InteractiveBuildStage, string> = {
  reading_lesson: "Reading your lesson",
  designing: "Designing the controls",
  building: "Building the interactive",
  checking: "Checking that it works",
};

const changeIdeas = [
  "Make it simpler for beginners",
  "Add a challenge with a target to reach",
  "Show more of the numbers behind it",
];

type StudioProps = Readonly<{
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
  interactiveId: string;
}>;

/** Describe it, watch it appear, try it, ask for changes: all on one page. */
export function InteractiveStudio({
  lesson,
  home,
  interactiveId,
}: StudioProps) {
  return interactiveId === "new" ? (
    <NewInteractive lesson={lesson} home={home} />
  ) : (
    <ExistingInteractive
      key={interactiveId}
      lesson={lesson}
      home={home}
      interactiveId={interactiveId}
    />
  );
}

function StudioShell({
  lesson,
  home,
  title,
  status,
  actions,
  stage,
  side,
}: {
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
  title: string;
  status?: ReactNode;
  actions?: ReactNode;
  stage: ReactNode;
  side: ReactNode;
}) {
  return (
    <div className="interactive-studio">
      <Link className="back-link" to={home.backTo}>
        ← {lesson.title} <span>/ Interactives</span>
      </Link>
      <div className="interactive-studio-heading">
        <h1>{title}</h1>
        {status}
        {actions && <div className="workflow-inline-actions">{actions}</div>}
      </div>
      <div className="interactive-studio-grid">
        <div className="interactive-studio-stage">{stage}</div>
        <aside className="interactive-studio-side">{side}</aside>
      </div>
    </div>
  );
}

function Composer({
  label,
  placeholder,
  action,
  initial = "",
  maxLength,
  problem,
  disabled,
  pending,
  ideas,
  onSubmit,
}: {
  label: string;
  placeholder: string;
  action: string;
  initial?: string;
  maxLength: number;
  problem(text: string): string | null;
  disabled: boolean;
  pending: boolean;
  ideas?: readonly string[];
  onSubmit(text: string, clear: () => void): void;
}) {
  const [text, setText] = useState(initial);
  const [touched, setTouched] = useState(false);
  const shown = touched ? problem(text) : null;
  const submit = () => {
    setTouched(true);
    if (problem(text) || disabled || pending) return;
    onSubmit(text, () => {
      setText("");
      setTouched(false);
    });
  };
  return (
    <form
      className="interactive-composer"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {!!ideas?.length && (
        <div className="interactive-chips">
          {ideas.map((idea) => (
            <button
              key={idea}
              type="button"
              disabled={disabled}
              onClick={() => setText(idea)}
            >
              {idea}
            </button>
          ))}
        </div>
      )}
      <label>
        <span>{label}</span>
        <textarea
          rows={4}
          value={text}
          maxLength={maxLength}
          placeholder={placeholder}
          disabled={disabled}
          autoFocus={!!initial}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              submit();
            }
          }}
        />
      </label>
      {shown && (
        <p className="quiz-problem" role="alert">
          {shown}
        </p>
      )}
      <Button type="submit" disabled={disabled || pending}>
        {pending ? "Starting…" : action}
      </Button>
    </form>
  );
}

function NewInteractive({
  lesson,
  home,
}: {
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
}) {
  const app = useApplication().interactives;
  const navigate = useNavigate();
  const location = useLocation();
  const [picked, setPicked] = useState(
    (location.state as { idea?: string } | null)?.idea ?? "",
  );
  const create = useInteractiveMutation((brief: string) => {
    if (!app) throw new Error("Interactives are unavailable.");
    return app.create({ lessonId: lesson.lessonId, brief });
  });
  const ideas = interactiveIdeas(lesson);
  return (
    <StudioShell
      lesson={lesson}
      home={home}
      title="New interactive"
      stage={
        <div className="interactive-blank">
          <h2>What should learners get to play with?</h2>
          <p className="muted">
            Say what they can change and what they should notice. It appears
            here to try, and you can ask for changes until it feels right.
          </p>
          {!!ideas.length && (
            <>
              <p className="muted small">Ideas from this lesson</p>
              <ul className="interactive-blank-ideas">
                {ideas.map((idea) => (
                  <li key={idea}>
                    <button type="button" onClick={() => setPicked(idea)}>
                      {idea}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      }
      side={
        <>
          <Composer
            key={picked}
            label="Describe your interactive"
            placeholder="e.g. A pendulum where learners change gravity, length and weight, and see how the swing changes."
            action="Build interactive"
            initial={picked}
            maxLength={interactiveLimits.brief}
            problem={briefProblem}
            disabled={!app}
            pending={create.isPending}
            onSubmit={(brief) =>
              create.mutate(brief, {
                onSuccess: (item) =>
                  navigate(interactivePath(home, item.id), { replace: true }),
              })
            }
          />
          <ErrorNotice error={create.error} />
        </>
      }
    />
  );
}

function BuildProgress({ stage }: { stage: InteractiveBuildStage }) {
  const at = interactiveBuildStages.indexOf(stage);
  return (
    <div className="interactive-building">
      <div className="interactive-sliders" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <h2>Building your interactive</h2>
      <ol role="status">
        {interactiveBuildStages.map((name, index) => (
          <li
            key={name}
            data-state={
              index < at ? "done" : index === at ? "current" : "upcoming"
            }
          >
            {stageLabels[name]}
          </li>
        ))}
      </ol>
      <p className="muted small">
        This keeps going if you leave this page. It will be here when you come
        back.
      </p>
    </div>
  );
}

function ExistingInteractive({ lesson, home, interactiveId }: StudioProps) {
  const query = useLessonInteractive(lesson.lessonId, interactiveId);
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  return <Workbench lesson={lesson} home={home} interactive={query.data} />;
}

function Workbench({
  lesson,
  home,
  interactive,
}: {
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
  interactive: LessonInteractive;
}) {
  const app = useApplication().interactives;
  const ref = { lessonId: interactive.lessonId, id: interactive.id };
  const [tab, setTab] = useState<"changes" | "learners">("changes");
  const [width, setWidth] = useState<"full" | "phone">("full");
  const need = () => {
    if (!app) throw new Error("Interactives are unavailable.");
    return app;
  };
  const change = useInteractiveMutation((instruction: string) =>
    need().requestChange({
      ...ref,
      instruction,
      expectedRevision: interactive.revision,
    }),
  );
  const retry = useInteractiveMutation(() => need().retryBuild(ref));
  const cancel = useInteractiveMutation(() => need().cancelBuild(ref));
  const restore = useInteractiveMutation((version: number) =>
    need().restoreVersion({
      ...ref,
      version,
      expectedRevision: interactive.revision,
    }),
  );
  const publish = useInteractiveMutation((version: number | null) =>
    need().setPublishedVersion({ ...ref, version }),
  );
  const state = interactiveState(interactive);
  const built = interactive.versions.length > 0;
  const building = !!interactive.build;
  const nextVersion = interactive.versions.length + 1;
  const title = built ? interactive.title : "New interactive";
  const actions =
    state === "draft" ? (
      <Button
        disabled={publish.isPending}
        onClick={() => publish.mutate(interactive.currentVersion)}
      >
        Add to lesson
      </Button>
    ) : state === "live_with_changes" ? (
      <>
        <Button
          variant="secondary"
          disabled={publish.isPending}
          onClick={() => publish.mutate(null)}
        >
          Remove from lesson
        </Button>
        <Button
          disabled={publish.isPending}
          onClick={() => publish.mutate(interactive.currentVersion)}
        >
          Use version {interactive.currentVersion} in lesson
        </Button>
      </>
    ) : state === "live" ? (
      <Button
        variant="secondary"
        disabled={publish.isPending}
        onClick={() => publish.mutate(null)}
      >
        Remove from lesson
      </Button>
    ) : null;
  const stage = interactive.html ? (
    <InteractiveStage
      html={interactive.html}
      title={title}
      width={width}
      tools={
        <div
          className="lesson-editor-tabs interactive-width"
          role="group"
          aria-label="Preview size"
        >
          <button
            type="button"
            aria-pressed={width === "full"}
            onClick={() => setWidth("full")}
          >
            Computer
          </button>
          <button
            type="button"
            aria-pressed={width === "phone"}
            onClick={() => setWidth("phone")}
          >
            Phone
          </button>
        </div>
      }
      notice={
        building && (
          <p className="interactive-stage-pill" role="status">
            <span className="loading-spinner" aria-hidden="true" />
            Building version {nextVersion}. You can keep trying this one.
          </p>
        )
      }
    />
  ) : interactive.build ? (
    <BuildProgress stage={interactive.build.stage} />
  ) : (
    <div className="interactive-blank interactive-failed" role="alert">
      <h2>This one didn’t finish</h2>
      <p className="muted">{interactive.failure?.message}</p>
      <div className="workflow-inline-actions">
        <Button disabled={retry.isPending} onClick={() => retry.mutate()}>
          Try again
        </Button>
      </div>
    </div>
  );
  return (
    <StudioShell
      lesson={lesson}
      home={home}
      title={title}
      status={<InteractiveStatus interactive={interactive} />}
      actions={actions}
      stage={
        <>
          {stage}
          {state === "live" && (
            <p className="interactive-live-note">
              Learners get this version.{" "}
              <Link to={`${home.lessonPath}?part=${interactive.id}`}>
                See it in the lesson
              </Link>
            </p>
          )}
          {state === "live_with_changes" && (
            <p className="interactive-live-note">
              Learners still get version {interactive.publishedVersion} until
              you choose this one.
            </p>
          )}
          {state === "draft" && (
            <p className="interactive-live-note">
              Only you can see this. Add it to the lesson when it’s ready for
              learners.
            </p>
          )}
          <ErrorNotice error={publish.error} />
        </>
      }
      side={
        <>
          <div
            className="lesson-editor-tabs interactive-side-tabs"
            role="group"
            aria-label="What would you like to work on?"
          >
            <button
              type="button"
              aria-pressed={tab === "changes"}
              onClick={() => setTab("changes")}
            >
              Changes
            </button>
            <button
              type="button"
              aria-pressed={tab === "learners"}
              onClick={() => setTab("learners")}
            >
              For learners
            </button>
          </div>
          {/* Both stay mounted, so switching never loses what was typed. */}
          <div className="interactive-side-pane" hidden={tab !== "changes"}>
            <History
              interactive={interactive}
              restoring={restore.isPending}
              stopping={cancel.isPending}
              retrying={retry.isPending}
              onRestore={(version) => restore.mutate(version)}
              onStop={() => cancel.mutate()}
              onRetry={() => retry.mutate()}
            />
            <ErrorNotice
              error={
                change.error ?? retry.error ?? cancel.error ?? restore.error
              }
            />
            <Composer
              label={built ? "Ask for a change" : "Change your description"}
              placeholder={
                built
                  ? "e.g. Add a slider for air resistance."
                  : "Say what learners should be able to do."
              }
              action={built ? "Make this change" : "Build interactive"}
              maxLength={interactiveLimits.change}
              problem={changeProblem}
              disabled={building || !app}
              pending={change.isPending}
              ideas={built && !building ? changeIdeas : undefined}
              onSubmit={(instruction, clear) =>
                change.mutate(instruction, { onSuccess: clear })
              }
            />
          </div>
          <div className="interactive-side-pane" hidden={tab !== "learners"}>
            <DetailsForm
              key={String(built)}
              interactive={interactive}
              disabled={!built}
            />
            <DeleteInteractive interactive={interactive} home={home} />
          </div>
        </>
      }
    />
  );
}

function History({
  interactive,
  restoring,
  stopping,
  retrying,
  onRestore,
  onStop,
  onRetry,
}: {
  interactive: LessonInteractive;
  restoring: boolean;
  stopping: boolean;
  retrying: boolean;
  onRestore(version: number): void;
  onStop(): void;
  onRetry(): void;
}) {
  const end = useRef<HTMLLIElement>(null);
  const turns = interactive.versions.length;
  const active = !!interactive.build || !!interactive.failure;
  useEffect(() => {
    const list = end.current?.parentElement;
    if (list) list.scrollTop = list.scrollHeight;
  }, [turns, active]);
  const { build, failure } = interactive;
  return (
    <ol className="interactive-history" aria-label="Version history">
      {interactive.versions.map((version) => (
        <li key={version.number}>
          <p className="interactive-request">{version.request}</p>
          <div className="interactive-version">
            <strong>Version {version.number}</strong>
            {version.number === interactive.publishedVersion && (
              <span>In lesson</span>
            )}
            {version.number === interactive.currentVersion ? (
              <span>Showing</span>
            ) : (
              <button
                type="button"
                disabled={restoring || !!build}
                onClick={() => onRestore(version.number)}
              >
                Go back to this
              </button>
            )}
          </div>
        </li>
      ))}
      {build && (
        <li>
          <p className="interactive-request">{build.request}</p>
          <div className="interactive-version" role="status">
            <span className="loading-spinner" aria-hidden="true" />
            <strong>{stageLabels[build.stage]}…</strong>
            <button type="button" disabled={stopping} onClick={onStop}>
              Stop building
            </button>
          </div>
        </li>
      )}
      {failure && !build && (
        <li>
          <p className="interactive-request">{failure.request}</p>
          <div className="interactive-version" data-failed="true">
            <strong>{failure.message}</strong>
            <button type="button" disabled={retrying} onClick={onRetry}>
              Try again
            </button>
          </div>
        </li>
      )}
      <li ref={end} className="interactive-history-end" aria-hidden="true" />
    </ol>
  );
}

function DetailsForm({
  interactive,
  disabled,
}: {
  interactive: LessonInteractive;
  disabled: boolean;
}) {
  const app = useApplication().interactives;
  const [title, setTitle] = useState(interactive.title);
  const [goal, setGoal] = useState(interactive.goal);
  const [prompts, setPrompts] = useState<readonly string[]>(
    interactive.prompts,
  );
  const [touched, setTouched] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const save = useInteractiveMutation(() => {
    if (!app) throw new Error("Interactives are unavailable.");
    return app.saveDetails({
      lessonId: interactive.lessonId,
      id: interactive.id,
      details: { title, goal, prompts },
      expectedRevision: interactive.revision,
    });
  });
  const problem = detailsProblem({ title, goal, prompts });
  const edited = () => {
    setJustSaved(false);
  };
  if (disabled)
    return (
      <p className="muted small">
        Once it’s built, you can set its title, its goal and what learners
        should try.
      </p>
    );
  return (
    <form
      className="interactive-details"
      onSubmit={(event) => {
        event.preventDefault();
        setTouched(true);
        if (problem || save.isPending) return;
        save.mutate(undefined, { onSuccess: () => setJustSaved(true) });
      }}
    >
      <label className="quiz-field">
        <span>Title</span>
        <input
          value={title}
          maxLength={interactiveLimits.title}
          onChange={(event) => {
            setTitle(event.target.value);
            edited();
          }}
        />
      </label>
      <label className="quiz-field">
        <span>What learners will figure out</span>
        <textarea
          rows={2}
          value={goal}
          maxLength={interactiveLimits.goal}
          onChange={(event) => {
            setGoal(event.target.value);
            edited();
          }}
        />
      </label>
      <div
        className="quiz-field"
        role="group"
        aria-label="Things for learners to try"
      >
        <span>Things to try</span>
        {prompts.map((prompt, index) => (
          <div className="quiz-option-row" key={index}>
            <textarea
              rows={2}
              aria-label={`Thing to try ${index + 1}`}
              value={prompt}
              maxLength={interactiveLimits.prompt}
              onChange={(event) => {
                setPrompts(
                  prompts.map((item, at) =>
                    at === index ? event.target.value : item,
                  ),
                );
                edited();
              }}
            />
            <button
              type="button"
              className="quiz-remove"
              aria-label={`Remove thing to try ${index + 1}`}
              onClick={() => {
                setPrompts(prompts.filter((_, at) => at !== index));
                edited();
              }}
            >
              ×
            </button>
          </div>
        ))}
        {prompts.length < interactiveLimits.prompts && (
          <button
            type="button"
            className="quiz-add-answer"
            onClick={() => {
              setPrompts([...prompts, ""]);
              edited();
            }}
          >
            + Add something to try
          </button>
        )}
      </div>
      {touched && problem && (
        <p className="quiz-problem" role="alert">
          {problem}
        </p>
      )}
      <div className="interactive-details-save">
        <Button type="submit" variant="secondary" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save details"}
        </Button>
        {justSaved && (
          <span className="muted small" role="status">
            Saved.
            {interactive.publishedVersion !== null &&
              " Learners see this right away."}
          </span>
        )}
      </div>
      <ErrorNotice error={save.error} />
    </form>
  );
}

function DeleteInteractive({
  interactive,
  home,
}: {
  interactive: LessonInteractive;
  home: InteractiveHome;
}) {
  const navigate = useNavigate();
  const remove = useRemoveInteractive(interactive.lessonId);
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="interactive-delete">
      {confirming ? (
        <>
          <p className="small">
            Delete this interactive and all its versions?
            {interactive.publishedVersion !== null &&
              " Learners will no longer see it."}
          </p>
          <div className="workflow-inline-actions">
            <Button
              variant="secondary"
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(interactive.id, {
                  onSuccess: () => navigate(home.backTo, { replace: true }),
                })
              }
            >
              {remove.isPending ? "Deleting…" : "Yes, delete it"}
            </Button>
            <Button
              variant="secondary"
              disabled={remove.isPending}
              onClick={() => setConfirming(false)}
            >
              Keep it
            </Button>
          </div>
        </>
      ) : (
        <button
          type="button"
          className="interactive-delete-open"
          onClick={() => setConfirming(true)}
        >
          Delete interactive
        </button>
      )}
      <ErrorNotice error={remove.error} />
    </div>
  );
}
