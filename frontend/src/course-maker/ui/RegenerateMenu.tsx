import { useEffect, useId, useRef, useState } from "react";
import type { RegenerationStep } from "../application/standalone-lessons";

export type RegenerationStart = RegenerationStep | "outline";

export type RegenerationOption = Readonly<{
  start: RegenerationStart;
  disabled?: boolean;
}>;

const stages = ["Outline", "Script", "Narration", "Animation"] as const;

const copy: Record<
  RegenerationStart,
  { title: string; detail: string; from: number }
> = {
  outline: {
    title: "Everything",
    detail: "A fresh outline, script, narration and animation.",
    from: 0,
  },
  script: {
    title: "From the script",
    detail: "Keeps your outline. Rewrites the script and everything after it.",
    from: 1,
  },
  speech: {
    title: "From the narration",
    detail: "Keeps your outline and script. Re-records the voice-over.",
    from: 2,
  },
  animation: {
    title: "Animation only",
    detail: "Keeps the words and voice. Redraws the visuals.",
    from: 3,
  },
};

/** Lets the creator rebuild the video from any finished stage onward. */
export function RegenerateMenu({
  options,
  disabled = false,
  primary = false,
  note,
  onSelect,
}: {
  options: readonly RegenerationOption[];
  disabled?: boolean;
  primary?: boolean;
  note?: string;
  onSelect(start: RegenerationStart): void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const isOpen = open && !disabled;
  useEffect(() => {
    // The panel opens upward, which can start above the viewport when the bar isn't pinned.
    if (isOpen) panel.current?.scrollIntoView?.({ block: "nearest" });
  }, [isOpen]);
  useEffect(() => {
    if (!isOpen) return;
    // Safari doesn't focus clicked buttons, so blur can't tell an option click from leaving.
    const closeOutside = (event: Event) => {
      if (event.target instanceof Node && !root.current?.contains(event.target))
        setOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("focusin", closeOutside);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("focusin", closeOutside);
    };
  }, [isOpen]);
  return (
    <div
      className="regenerate-menu"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === "Escape" && isOpen) {
          setOpen(false);
          toggle.current?.focus();
        }
      }}
    >
      <button
        ref={toggle}
        type="button"
        className={`btn btn-${primary ? "primary" : "secondary"}`}
        aria-expanded={isOpen}
        aria-controls={panelId}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        {primary ? "Regenerate video" : "Regenerate"}
        <span className="chevron" aria-hidden="true" />
      </button>
      {isOpen && (
        <div
          ref={panel}
          id={panelId}
          className="regenerate-panel"
          role="group"
          aria-label="Regenerate video"
        >
          <p className="regenerate-heading">What should we rebuild?</p>
          {options.map(({ start, disabled: unavailable }) => {
            const option = copy[start];
            return (
              <button
                key={start}
                type="button"
                className="regenerate-option"
                disabled={unavailable}
                aria-labelledby={`${panelId}-${start}`}
                aria-describedby={`${panelId}-${start}-detail`}
                onClick={() => {
                  setOpen(false);
                  onSelect(start);
                }}
              >
                <strong id={`${panelId}-${start}`}>{option.title}</strong>
                <span id={`${panelId}-${start}-detail`} className="muted small">
                  {option.detail}
                </span>
                <span className="regenerate-stages" aria-hidden="true">
                  {stages.map((stage, index) => (
                    <span
                      key={stage}
                      data-state={index < option.from ? "kept" : "rebuilt"}
                    >
                      {stage}
                    </span>
                  ))}
                </span>
              </button>
            );
          })}
          {note && <p className="regenerate-note muted small">{note}</p>}
        </div>
      )}
    </div>
  );
}

/** Describes what generating rebuilds when saved edits removed later stages. */
export function rebuildSummary(content: {
  storyboard: unknown;
  alignment: unknown;
  animation: unknown;
}) {
  return !content.storyboard
    ? "the script, narration and animation"
    : !content.alignment
      ? "the narration and animation"
      : !content.animation
        ? "the animation"
        : null;
}
