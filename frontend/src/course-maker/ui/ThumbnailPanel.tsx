import { useActivity } from "./activity";
import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ThumbnailRequest } from "../application/thumbnails";
import type { CourseResponse } from "../application/dto";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { useApplication } from "./application-context";
import { ErrorNotice, Thumbnail } from "./components";
import { Button } from "./primitives/Button";

export function ThumbnailPanel(
  props: ThumbnailRequest & {
    image: string;
    disabled?: boolean;
    preparing?: boolean;
    onBusyChange?(busy: boolean): void;
    onSaved?(result: CourseResponse | StandaloneLessonResponse): void;
  },
) {
  const app = useApplication().thumbnails;
  const cache = useQueryClient();
  const key = props.kind === "course" ? "courses" : "lessons";
  const activeOperation = useActivity(props.kind, props.id, true);
  const mutation = useMutation({
    mutationFn: () => {
      if (!app)
        throw new Error("Connect to the server to generate a thumbnail.");
      return app.execute({
        kind: props.kind,
        id: props.id,
        lessonId: props.lessonId,
        regenerate: !!props.image,
      });
    },
    onSuccess: (result) => {
      cache.setQueryData([key, props.id], result);
      props.onSaved?.(result);
      void cache.invalidateQueries({ queryKey: [key] });
    },
    onError: () => {
      void cache.invalidateQueries({ queryKey: [key] });
    },
  });
  const onBusyChange = props.onBusyChange;
  const pending = mutation.isPending || activeOperation.endsWith("thumbnail");
  useEffect(() => {
    onBusyChange?.(pending);
    return () => onBusyChange?.(false);
  }, [pending, onBusyChange]);
  if (!app) return null;
  return (
    <section
      className="style-panel"
      aria-label="Thumbnail"
      aria-busy={pending || props.preparing}
    >
      <div className="style-heading">
        <Thumbnail name={props.image} variant="course" />
        <div>
          <p className="eyebrow">THUMBNAIL</p>
          <p className="muted small">
            An illustration of your topic, in our shared visual style.
          </p>
          {!props.image && !props.preparing && !pending && (
            <p className="muted small">
              Your draft is saved. Generate its thumbnail when you’re ready.
            </p>
          )}
        </div>
        <Button
          variant="secondary"
          disabled={props.disabled || pending}
          onClick={() => mutation.mutate()}
        >
          {pending
            ? "Drawing thumbnail…"
            : props.image
              ? "Regenerate thumbnail"
              : "Generate thumbnail"}
        </Button>
      </div>
      {(pending || props.preparing) && (
        <p role="status" className="muted small">
          <span className="loading-spinner" aria-hidden="true" />
          Drawing your illustration…
        </p>
      )}
      <ErrorNotice error={mutation.error} />
    </section>
  );
}
