import { useState, type ReactNode } from "react";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { useApplication } from "./application-context";
import { useLessonMutation } from "./lesson-context";
import { ErrorNotice } from "./components";
import { Button } from "./primitives/Button";

export function LessonScript({
  lesson,
  disabled = false,
  actions,
  onDirtyChange,
}: {
  lesson: StandaloneLessonResponse;
  disabled?: boolean;
  /** Extra heading actions, shown while the script isn't being edited. */
  actions?: ReactNode;
  onDirtyChange(dirty: boolean): void;
}) {
  const app = useApplication().lessons;
  const [draft, setDraft] = useState<{
    revision: number;
    narrations: string[];
  } | null>(null);
  const save = useLessonMutation(async () => {
    if (!app?.saveScript || !draft)
      throw new Error("Script editing is unavailable.");
    const result = await app.saveScript.execute({
      id: lesson.id,
      expectedRevision: draft.revision,
      narrations: draft.narrations,
    });
    setDraft(null);
    onDirtyChange(false);
    return result;
  });
  const script = lesson.content.storyboard;
  if (!script) return null;
  return (
    <section className="lesson-script" aria-label="Video script">
      <div className="workflow-section-heading">
        <div>
          <h2>Script & narration</h2>
          <p className="muted small">
            Review the words before creating your video.
          </p>
        </div>
        {!draft && (
          <div className="workflow-inline-actions">
            {actions}
            <Button
              variant="secondary"
              disabled={disabled || !app?.saveScript}
              onClick={() => {
                setDraft({
                  revision: lesson.revision,
                  narrations: script.scenes.map((s) => s.narrationText),
                });
                onDirtyChange(true);
              }}
            >
              Edit script
            </Button>
          </div>
        )}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {script.scenes.map((scene, index) => (
          <article className="script-scene" key={index}>
            <h3>Scene {index + 1}</h3>
            {draft ? (
              <label>
                Narration for scene {index + 1}
                <textarea
                  aria-label={`Narration for scene ${index + 1}`}
                  required
                  maxLength={16000}
                  rows={5}
                  value={draft.narrations[index]}
                  disabled={disabled || save.isPending}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      narrations: draft.narrations.map((text, i) =>
                        i === index ? event.target.value : text,
                      ),
                    })
                  }
                />
              </label>
            ) : (
              <p>{scene.narrationText}</p>
            )}
          </article>
        ))}
        {draft && (
          <>
            <p className="workflow-impact">
              Saving script changes rebuilds narration and video on the next
              generation. Your current video stays available.
            </p>
            <div className="workflow-inline-actions">
              <Button type="submit" disabled={disabled || save.isPending}>
                Save script
              </Button>
              <Button
                variant="secondary"
                disabled={save.isPending}
                onClick={() => {
                  setDraft(null);
                  onDirtyChange(false);
                  save.reset();
                }}
              >
                Cancel script edits
              </Button>
            </div>
          </>
        )}
        <ErrorNotice error={save.error} />
      </form>
    </section>
  );
}
