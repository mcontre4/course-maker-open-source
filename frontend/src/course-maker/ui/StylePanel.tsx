import { useActivity } from "./activity";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  styleInputFromResponse,
  type StyleInput,
  type StyleResponse,
} from "../application/style";
import type { GenerationMode } from "../application/generation-mode";
import { useApplication } from "./application-context";
import { StyleFields, visualStyleName } from "./StyleFields";
import { Button } from "./primitives/Button";
import { ErrorNotice } from "./components";

export function StylePanel(props: {
  id: string;
  kind: "course" | "lesson";
  lessonId?: string;
  style?: StyleResponse | null;
  inherited?: StyleResponse | null;
  history?: readonly StyleResponse[];
  generationMode?: GenerationMode;
  disabled?: boolean;
  preparing?: boolean;
  focus?: "voice" | "visuals";
  onBusyChange?(busy: boolean): void;
  onDirtyChange?(dirty: boolean): void;
}) {
  const effective = props.style ?? props.inherited;
  const [saved, setSaved] = useState(false);
  return (
    <StyleEditor
      // A focused editor stays open, so a newly saved version restarts it from the saved values.
      key={`${props.kind}:${props.id}:${props.lessonId ?? ""}:${props.focus ?? "all"}:${props.focus ? (effective?.version ?? 0) : ""}`}
      {...props}
      effective={effective}
      saved={saved}
      onSavedChange={setSaved}
    />
  );
}

function StyleEditor({
  effective,
  saved,
  onSavedChange,
  ...props
}: Parameters<typeof StylePanel>[0] & {
  effective?: StyleResponse | null;
  saved: boolean;
  onSavedChange(saved: boolean): void;
}) {
  const app = useApplication();
  const cache = useQueryClient();
  const initial = styleInputFromResponse(effective);
  const [value, setValue] = useState(initial);
  const [editing, setEditing] = useState(!!props.focus);
  const dirty = editing && JSON.stringify(initial) !== JSON.stringify(value);
  const activeOperation = useActivity(props.kind, props.id);
  const save = useMutation({
    mutationFn: (style: StyleInput | null) =>
      app.styles!.update.execute({
        id: props.id,
        kind: props.kind,
        lessonId: props.lessonId,
        style,
        expectedVersion: props.style?.version ?? 0,
        generationMode: props.generationMode,
      }),
    onSuccess: (result) => {
      const key = props.kind === "course" ? "courses" : "lessons";
      cache.setQueryData([key, props.id], result);
      void cache.invalidateQueries({ queryKey: [key] });
      if (!props.focus) setEditing(false);
      onSavedChange(true);
    },
    onError: () => {
      void cache.invalidateQueries({
        queryKey: [props.kind === "course" ? "courses" : "lessons", props.id],
      });
    },
  });
  const pending = save.isPending || activeOperation.endsWith("style");
  useEffect(() => {
    props.onBusyChange?.(pending);
    return () => props.onBusyChange?.(false);
  }, [pending, props.onBusyChange]);
  useEffect(() => {
    props.onDirtyChange?.(dirty);
    if (dirty) onSavedChange(false);
    return () => props.onDirtyChange?.(false);
  }, [dirty, props.onDirtyChange, onSavedChange]);
  const visualStyle = visualStyleName(
    effective ? (effective.visualStyleId ?? "flat-vector-science") : undefined,
  );
  const summary = effective && (
    <p className="muted small">
      Narrator: {effective.voiceName} · Style version {effective.version}
      {visualStyle ? ` · ${visualStyle}` : ""}
      {" · "}
      {effective.reviewOutput === false
        ? "I'll review the video myself"
        : "AI review enabled"}
      {props.lessonId && !props.style ? " · Inherited from course" : ""}
    </p>
  );
  const directions = effective && (
    <details>
      <summary>View style directions</summary>
      <dl className="style-directions">
        {(
          [
            ["Audience", effective.audience],
            ["Teaching", effective.teaching],
            ["Writing", effective.writing],
            ["Visuals", effective.visuals],
            ["Motion", effective.motion],
            ["Pacing", effective.pacing],
            ["Voice", effective.voiceDescription],
            ["Delivery", effective.delivery],
            ["Accent", effective.accent ?? "American"],
            ["Tone", effective.tone || "Automatic — match topic and audience"],
          ] as const
        )
          .filter(([, text]) => text)
          .map(([label, text]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{text}</dd>
            </div>
          ))}
      </dl>
    </details>
  );
  const status = (
    <>
      {(pending || props.preparing) && (
        <p role="status" className="muted small">
          <span className="loading-spinner" aria-hidden="true" />
          Planning your lesson style…
        </p>
      )}
      {effective?.voiceNotice && (
        <p role="status" className="muted small">
          {effective.voiceNotice}
        </p>
      )}
    </>
  );
  const history = !!props.history?.length && (
    <details>
      <summary>Previous style versions ({props.history.length})</summary>
      <ul>
        {props.history.map((style, index) => (
          <li key={index}>
            Version {style.version}: {style.summary} — {style.voiceName}
          </li>
        ))}
      </ul>
    </details>
  );
  const fields = (
    <StyleFields
      value={value}
      onChange={setValue}
      embedded
      focus={props.focus}
      label={
        props.kind === "course" && !props.lessonId
          ? "Course style"
          : "Lesson style"
      }
      disabled={pending || props.disabled}
      currentVoiceName={effective?.voiceName}
      recommendedVoiceId={effective?.voiceId}
    />
  );
  if (props.focus)
    return (
      <section
        className="style-panel style-focus"
        aria-busy={pending || props.preparing}
        aria-label={
          props.focus === "voice" ? "Voice & delivery" : "Visual style"
        }
      >
        <div className="workflow-section-heading">
          <div>
            <h2>
              {props.focus === "voice" ? "Voice & delivery" : "Visual style"}
            </h2>
            {summary ?? (
              <p className="muted small">
                Your style is planned with the outline.
              </p>
            )}
          </div>
        </div>
        {status}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(value);
          }}
        >
          {fields}
          <p className="muted small">
            {props.focus === "voice"
              ? "Saving voice changes re-records the narration when you generate the video."
              : "Saving visual changes redraws the animation when you generate the video."}{" "}
            Your current video stays available until then.
          </p>
          <div className="workflow-inline-actions">
            <Button
              type="submit"
              disabled={pending || props.disabled || !dirty}
            >
              {pending
                ? "Saving preferences…"
                : props.focus === "voice"
                  ? "Save voice"
                  : "Save visuals"}
            </Button>
            {dirty && (
              <Button
                variant="secondary"
                disabled={pending}
                onClick={() => setValue(initial)}
              >
                Discard changes
              </Button>
            )}
          </div>
          {saved && !dirty && (
            <p role="status" className="style-saved">
              ✓ Saved. Generate an updated video to see the change.
            </p>
          )}
        </form>
        {directions}
        {history}
        <ErrorNotice error={save.error} />
      </section>
    );
  return (
    <details
      className="style-panel advanced-settings"
      aria-busy={pending || props.preparing}
      aria-label={
        props.kind === "course" && !props.lessonId
          ? "Course style"
          : "Lesson style"
      }
    >
      <summary>Advanced settings</summary>
      <div className="style-heading">
        <div>
          <p className="eyebrow">
            {props.kind === "course" && !props.lessonId
              ? "COURSE STYLE"
              : "LESSON STYLE"}
          </p>
          <p>
            {effective?.summary ??
              "Clear, approachable teaching. Style will follow your learning prompt."}
          </p>
          {summary}
        </div>
        {app.styles && (
          <Button
            disabled={props.disabled || pending}
            onClick={() => {
              setValue(initial);
              setEditing(!editing);
            }}
          >
            {editing ? "Cancel style edit" : "Edit style"}
          </Button>
        )}
      </div>
      {status}
      {directions}
      {editing && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(value);
          }}
        >
          {fields}
          <p className="muted small">
            Voice changes rebuild narration and animation. Visual changes
            rebuild the storyboard and downstream media. Teaching or writing
            changes also rebuild the outline. Previous versions stay saved.
          </p>
          <Button type="submit" disabled={pending || props.disabled || !dirty}>
            {pending ? "Saving preferences…" : "Save style"}
          </Button>
          {props.lessonId && props.style && (
            <Button
              type="button"
              disabled={pending || props.disabled}
              onClick={() => save.mutate(null)}
            >
              Use course style
            </Button>
          )}
        </form>
      )}
      {history}
      <ErrorNotice error={save.error} />
    </details>
  );
}
