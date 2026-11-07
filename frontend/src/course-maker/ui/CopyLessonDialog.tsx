import { useEffect, useId, useRef, useState } from "react";
import { ErrorNotice, Thumbnail } from "./components";
import { Button } from "./primitives/Button";

const TITLE_LIMIT = 120;
const COUNTER_FROM = 100;

/** Mirrors the name the server gives a copy when none is chosen. */
export function suggestCopyTitle(title: string) {
  return title.slice(0, TITLE_LIMIT - 5).trimEnd() + "-copy";
}

export function CopyLessonDialog({
  title,
  image,
  pending,
  error,
  onSubmit,
  onClose,
}: {
  title: string;
  image: string;
  pending: boolean;
  error: unknown;
  onSubmit(title: string): void;
  onClose(): void;
}) {
  const id = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const pressedBackdrop = useRef(false);
  const [name, setName] = useState(() => suggestCopyTitle(title));
  const trimmed = name.trim();

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    element.showModal();
    field.current?.focus();
    field.current?.select();
    return () => {
      if (element.open) element.close();
    };
  }, []);

  return (
    <dialog
      ref={dialog}
      className="copy-sheet"
      aria-labelledby={`${id}-heading`}
      aria-describedby={`${id}-about`}
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        if (!pending) onClose();
      }}
      onMouseDown={(event) => {
        pressedBackdrop.current = event.target === event.currentTarget;
      }}
      onClick={(event) => {
        if (
          pressedBackdrop.current &&
          event.target === event.currentTarget &&
          !pending
        )
          onClose();
        pressedBackdrop.current = false;
      }}
    >
      <form
        className="copy-sheet-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (trimmed && !pending) onSubmit(trimmed);
        }}
      >
        <div className="copy-sheet-art" data-empty={!image || undefined}>
          <span className="copy-sheet-ghost copy-sheet-ghost-back" />
          <span className="copy-sheet-ghost copy-sheet-ghost-front" />
          <div className="copy-sheet-cover">
            {image ? (
              <Thumbnail name={image} variant="course" />
            ) : (
              <span className="copy-sheet-blank" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <rect x="3" y="5" width="18" height="14" rx="3" />
                  <path d="m3 16 5-4.5 4 3.5 3-2.5 6 4.5" />
                </svg>
              </span>
            )}
          </div>
        </div>
        <div className="copy-sheet-body">
          <h2 id={`${id}-heading`}>Copy this lesson</h2>
          <p id={`${id}-about`} className="copy-sheet-about">
            You get your own version to edit and regenerate. The original stays
            as it is.
          </p>
          <label className="copy-sheet-field" htmlFor={`${id}-title`}>
            <span>Title</span>
            <input
              id={`${id}-title`}
              ref={field}
              value={name}
              maxLength={TITLE_LIMIT}
              autoComplete="off"
              spellCheck
              disabled={pending}
              aria-invalid={!trimmed || undefined}
              aria-describedby={`${id}-note`}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <p id={`${id}-note`} className="copy-sheet-note">
            <span>
              {image
                ? "The thumbnail comes with it. You can regenerate it in the copy."
                : "No thumbnail yet. You can add one in the copy."}
            </span>
            {name.length >= COUNTER_FROM && (
              <span className="copy-sheet-count" aria-live="polite">
                {name.length}/{TITLE_LIMIT}
              </span>
            )}
          </p>
          <ErrorNotice error={error} />
        </div>
        <div className="copy-sheet-actions">
          <Button variant="secondary" disabled={pending} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!trimmed || pending}>
            {pending ? (
              <>
                <span className="loading-spinner" aria-hidden="true" />
                Creating copy…
              </>
            ) : (
              "Create copy"
            )}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
