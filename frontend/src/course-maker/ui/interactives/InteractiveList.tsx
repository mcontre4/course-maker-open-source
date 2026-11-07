import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  interactiveIdeas,
  interactiveLimits,
  interactiveState,
  type InteractiveLessonContext,
  type LessonInteractive,
} from "../../application/lesson-interactives";
import { ErrorNotice, LinkButton } from "../components";
import {
  useLessonInteractives,
  useReorderInteractives,
} from "../lesson-interactive-context";
import { Button } from "../primitives/Button";
import { InteractiveFrame } from "./InteractiveFrame";
import { InteractiveStatus } from "./InteractiveStatus";
import { interactivePath, type InteractiveHome } from "./interactive-paths";

function InteractiveCard({
  interactive,
  home,
  position,
  total,
  onMove,
  disabled,
}: {
  interactive: LessonInteractive;
  home: InteractiveHome;
  position: number;
  total: number;
  onMove(by: -1 | 1): void;
  disabled: boolean;
}) {
  const failed = interactiveState(interactive) === "failed";
  return (
    <li className="interactive-card">
      <Link
        className="interactive-card-open"
        to={interactivePath(home, interactive.id)}
      >
        <span className="interactive-thumb" aria-hidden="true">
          {interactive.html ? (
            <InteractiveFrame
              decorative
              html={interactive.html}
              title=""
              className="interactive-thumb-frame"
            />
          ) : (
            <span className="interactive-thumb-empty" data-failed={failed} />
          )}
        </span>
        <span className="interactive-card-copy">
          <strong>
            {interactive.versions.length
              ? interactive.title
              : interactive.brief}
          </strong>
          <small>
            {interactive.goal ||
              (failed
                ? "Open it to try again."
                : "Building from your description…")}
          </small>
        </span>
      </Link>
      <div className="interactive-card-side">
        <InteractiveStatus interactive={interactive} />
        {total > 1 && (
          <div className="quiz-card-tools">
            <button
              type="button"
              aria-label={`Move ${interactive.title} earlier`}
              disabled={disabled || position === 0}
              onClick={() => onMove(-1)}
            >
              ↑
            </button>
            <button
              type="button"
              aria-label={`Move ${interactive.title} later`}
              disabled={disabled || position === total - 1}
              onClick={() => onMove(1)}
            >
              ↓
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

/** Ideas drawn from the lesson. Picking one opens the builder with it filled in. */
function IdeaList({
  lesson,
  home,
}: {
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
}) {
  const navigate = useNavigate();
  const ideas = interactiveIdeas(lesson);
  if (!ideas.length) return null;
  return (
    <div className="interactive-ideas">
      <p className="muted small">Start from an idea</p>
      <ul>
        {ideas.map((idea) => (
          <li key={idea}>
            <button
              type="button"
              onClick={() =>
                navigate(interactivePath(home, "new"), { state: { idea } })
              }
            >
              {idea}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Everything a creator has built for a lesson, and the way to build another. */
export function LessonInteractivesPanel({
  lesson,
  home,
}: {
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
}) {
  const navigate = useNavigate();
  const query = useLessonInteractives(lesson.lessonId);
  const reorder = useReorderInteractives(lesson.lessonId);
  const [order, setOrder] = useState<readonly string[] | null>(null);
  const items = query.data ?? [];
  const sorted = order
    ? [...items].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
    : items;
  const full = items.length >= interactiveLimits.perLesson;
  const move = (index: number, by: -1 | 1) => {
    const ids = sorted.map((item) => item.id);
    [ids[index], ids[index + by]] = [ids[index + by], ids[index]];
    setOrder(ids);
    reorder.mutate(ids, { onSettled: () => setOrder(null) });
  };
  if (query.isPending)
    return (
      <section className="lesson-quiz" aria-label="Lesson interactives">
        <p className="quiz-empty" role="status">
          <span className="loading-spinner" aria-hidden="true" />
          Loading your interactives…
        </p>
      </section>
    );
  if (!items.length)
    return (
      <section
        className="interactive-panel interactive-panel-empty"
        aria-labelledby="interactive-panel-title"
      >
        <h2 id="interactive-panel-title">Let learners try it themselves</h2>
        <p className="muted">
          Describe something learners can play with, like a pendulum where they
          change gravity and length. You can do this before, during or after
          making your video.
        </p>
        <ErrorNotice error={query.error} />
        <Button onClick={() => navigate(interactivePath(home, "new"))}>
          Describe an interactive
        </Button>
        <IdeaList lesson={lesson} home={home} />
      </section>
    );
  return (
    <section
      className="interactive-panel"
      aria-labelledby="interactive-panel-title"
    >
      <div className="workflow-section-heading">
        <div>
          <h2 id="interactive-panel-title">Interactives</h2>
          <p className="muted small">
            Learners meet them in this order, after the video.
          </p>
        </div>
        <div className="workflow-inline-actions">
          <Button
            variant="secondary"
            disabled={full}
            onClick={() => navigate(interactivePath(home, "new"))}
          >
            New interactive
          </Button>
        </div>
      </div>
      <ol className="interactive-cards">
        {sorted.map((interactive, index) => (
          <InteractiveCard
            key={interactive.id}
            interactive={interactive}
            home={home}
            position={index}
            total={sorted.length}
            disabled={reorder.isPending}
            onMove={(by) => move(index, by)}
          />
        ))}
      </ol>
      {full && (
        <p className="muted small">
          A lesson can have up to {interactiveLimits.perLesson} interactives.
          Delete one to add another.
        </p>
      )}
      <ErrorNotice error={query.error ?? reorder.error} />
    </section>
  );
}

/** Shown on the progress screens, so waiting for a video is time to build something. */
export function InteractivesWhileYouWait({
  lesson,
  home,
}: {
  lesson: InteractiveLessonContext;
  home: InteractiveHome;
}) {
  const query = useLessonInteractives(lesson.lessonId);
  const items = query.data ?? [];
  if (query.isPending) return null;
  return (
    <section
      className="interactive-wait"
      aria-labelledby="interactive-wait-title"
    >
      <div>
        <h2 id="interactive-wait-title">
          {items.length
            ? "Interactives for this lesson"
            : "While you wait, add something learners can try"}
        </h2>
        <p className="muted small">
          {items.length
            ? "They keep building on their own, and your video keeps going if you leave this page."
            : "Describe an interactive now. Your video keeps going while you work on it."}
        </p>
      </div>
      {!!items.length && (
        <ul className="interactive-wait-list">
          {items.map((item) => (
            <li key={item.id}>
              <Link to={interactivePath(home, item.id)}>
                {item.versions.length ? item.title : item.brief}
              </Link>
              <InteractiveStatus interactive={item} />
            </li>
          ))}
        </ul>
      )}
      <LinkButton secondary to={interactivePath(home, "new")}>
        {items.length ? "New interactive" : "Describe an interactive"}
      </LinkButton>
    </section>
  );
}
