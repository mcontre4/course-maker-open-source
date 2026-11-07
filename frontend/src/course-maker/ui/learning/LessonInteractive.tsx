import { useEffect, useRef, useState } from "react";
import type { InteractiveResponse } from "../../application/dto";
import { InteractiveFrame } from "../interactives/InteractiveFrame";
import "./lesson-interactive.css";

export function LessonInteractive({
  interactive,
  editing = false,
}: {
  interactive?: InteractiveResponse | null;
  editing?: boolean;
}) {
  const surface = useRef<HTMLElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [fullscreenError, setFullscreenError] = useState(false);
  useEffect(() => {
    const changed = () =>
      setExpanded(document.fullscreenElement === surface.current);
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);
  if (!interactive) return null;
  const { spec, html, reason } = interactive;
  if (!spec || !html)
    return editing ? (
      <details className="interactive-decision">
        <summary>No interactive needed for this lesson</summary>
        <p>{reason}</p>
      </details>
    ) : null;
  const frame = (
    <InteractiveFrame
      html={html}
      title={spec.title}
      className="lesson-interactive-frame"
    />
  );
  return (
    <section
      ref={surface}
      className="lesson-interactive"
      aria-label="Lesson interactive"
    >
      <div className="interactive-heading">
        <div>
          <p className="eyebrow">INTERACTIVE</p>
          <h2>{spec.title}</h2>
        </div>
        {globalThis.document.fullscreenEnabled && (
          <button
            type="button"
            className="interactive-expand"
            onClick={async () => {
              setFullscreenError(false);
              try {
                if (expanded) await globalThis.document.exitFullscreen();
                else await surface.current?.requestFullscreen();
              } catch {
                setFullscreenError(true);
              }
            }}
          >
            {expanded ? "Collapse ↙" : "Expand ↗"}
          </button>
        )}
      </div>
      <p className="muted">{spec.objective}</p>
      {fullscreenError && (
        <p role="alert">
          Fullscreen is unavailable. You can still use the activity here.
        </p>
      )}
      {frame}
      {editing && (
        <details className="interactive-decision">
          <summary>Why this activity?</summary>
          <p>{reason}</p>
        </details>
      )}
    </section>
  );
}
