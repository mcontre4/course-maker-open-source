import { useEffect, useState, type ReactNode, type RefObject } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  learnerView,
  type LearnerInteractive,
  type LessonInteractive,
} from "../../application/lesson-interactives";
import { InteractiveStage } from "./InteractiveStage";
import { useCurrentInStrip } from "../use-current-in-strip";

/** One stop on the way through a lesson. */
export type LessonPart = Readonly<{
  id: string;
  title: string;
  detail: string;
}>;

const part = "part";

/** The stop being shown lives in the address, so it survives Back and can be linked to. */
export function useLessonPart(parts: readonly LessonPart[]) {
  const [params, setParams] = useSearchParams();
  const requested = params.get(part);
  const active = parts.some((item) => item.id === requested)
    ? requested!
    : (parts[0]?.id ?? "video");
  const select = (id: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (id === parts[0]?.id) next.delete(part);
        else next.set(part, id);
        return next;
      },
      { preventScrollReset: true },
    );
  return { active, select };
}

/** Keeps a hidden video's place, but stops it from playing out of sight. */
export function usePausedWhenHidden(
  surface: RefObject<HTMLElement | null>,
  hidden: boolean,
) {
  useEffect(() => {
    if (!hidden || !surface.current) return;
    surface.current.querySelectorAll("video").forEach((video) => video.pause());
    surface.current
      .querySelectorAll("iframe")
      .forEach((frame) =>
        frame.contentWindow?.postMessage(
          { channel: "lesson-preview", type: "pause" },
          "*",
        ),
      );
  }, [surface, hidden]);
}

/** Watch, try, check: the order a lesson is meant to be taken in. */
export function LessonPath({
  parts,
  active,
  onSelect,
  add,
}: {
  parts: readonly LessonPart[];
  active: string;
  onSelect(id: string): void;
  /** Creators get one more stop at the end, for adding to the path. */
  add?: Readonly<{ to: string; label: string; detail: string }>;
}) {
  const strip = useCurrentInStrip("step", active);
  return (
    <nav ref={strip} className="lesson-path" aria-label="Parts of this lesson">
      <ol>
        {parts.map((item, index) => (
          <li key={item.id}>
            <button
              type="button"
              aria-current={item.id === active ? "step" : undefined}
              onClick={() => onSelect(item.id)}
            >
              <b aria-hidden="true">{index + 1}</b>
              <span>
                <strong>{item.title}</strong>
                <small>{item.detail}</small>
              </span>
            </button>
          </li>
        ))}
        {add && (
          <li className="lesson-path-add">
            <Link to={add.to}>
              <b aria-hidden="true">+</b>
              <span>
                <strong>{add.label}</strong>
                <small>{add.detail}</small>
              </span>
            </Link>
          </li>
        )}
      </ol>
    </nav>
  );
}

export function NextPart({
  parts,
  active,
  onSelect,
}: {
  parts: readonly LessonPart[];
  active: string;
  onSelect(id: string): void;
}) {
  const at = parts.findIndex((item) => item.id === active);
  const next = parts[at + 1];
  if (!next) return null;
  return (
    <div className="lesson-path-next">
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => {
          onSelect(next.id);
          document.querySelector(".lesson-path")?.scrollIntoView?.();
        }}
      >
        Next: {next.title}
      </button>
    </div>
  );
}

/** An interactive as learners get it: what to figure out, the thing itself, and what to try. */
export function LearnerInteractiveView({
  interactive,
  action,
  checked,
  onToggle,
}: {
  interactive: LearnerInteractive;
  action?: ReactNode;
  checked: ReadonlySet<number>;
  onToggle(index: number): void;
}) {
  return (
    <section
      className="learner-interactive"
      aria-labelledby={`interactive-${interactive.id}`}
    >
      <div className="learner-interactive-heading">
        <div>
          <h2 id={`interactive-${interactive.id}`}>{interactive.title}</h2>
          {interactive.goal && <p className="muted">{interactive.goal}</p>}
        </div>
        {action}
      </div>
      <div
        className="learner-interactive-body"
        data-has-prompts={interactive.prompts.length > 0}
      >
        <InteractiveStage html={interactive.html} title={interactive.title} />
        {interactive.prompts.length > 0 && (
          <aside className="learner-try" aria-label="Things to try">
            <h3>Things to try</h3>
            <ul>
              {interactive.prompts.map((prompt, index) => (
                <li key={index}>
                  <label data-checked={checked.has(index)}>
                    <input
                      type="checkbox"
                      checked={checked.has(index)}
                      onChange={() => onToggle(index)}
                    />
                    <span>{prompt}</span>
                  </label>
                </li>
              ))}
            </ul>
            <p className="muted small" role="status">
              {checked.size === interactive.prompts.length
                ? "You tried them all."
                : `${checked.size} of ${interactive.prompts.length} tried`}
            </p>
          </aside>
        )}
      </div>
    </section>
  );
}

/** Ticks stay while moving around the lesson; each interactive keeps its own. */
export function useTriedPrompts() {
  const [tried, setTried] = useState<ReadonlyMap<string, ReadonlySet<number>>>(
    new Map(),
  );
  return {
    checked: (id: string): ReadonlySet<number> => tried.get(id) ?? new Set(),
    toggle: (id: string, index: number) =>
      setTried((current) => {
        const next = new Set(current.get(id));
        if (next.has(index)) next.delete(index);
        else next.add(index);
        return new Map(current).set(id, next);
      }),
  };
}

/** What learners currently get, for pages that hold the creator's full list. */
export function liveInteractives(
  interactives: readonly LessonInteractive[],
): readonly LearnerInteractive[] {
  return interactives.flatMap((item) => {
    const view = learnerView(item);
    return view ? [view] : [];
  });
}

export function interactiveParts(
  interactives: readonly LearnerInteractive[],
): readonly LessonPart[] {
  return interactives.map((item) => ({
    id: item.id,
    title: item.title,
    detail: "Try it yourself",
  }));
}
