import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useApplication } from "./application-context";
import { ErrorNotice } from "./components";
import { Button } from "./primitives/Button";

export function CancelGenerationButton({
  kind,
  id,
  pending,
  operation,
  label = "generation",
}: {
  kind: "course" | "lesson";
  id: string;
  pending: boolean;
  operation?: string;
  label?: string;
}) {
  const cancel = useApplication().cancelGeneration;
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: async () => {
      if (!cancel) throw new Error("Cancellation is unavailable.");
      if (!(await cancel.execute({ kind, id })))
        throw new Error(
          "No active generation was found. Reload or try again shortly.",
        );
    },
    onSettled: () => {
      void cache.invalidateQueries({
        queryKey: [kind === "course" ? "courses" : "lessons", id],
      });
    },
  });
  const reset = mutation.reset;
  useEffect(() => {
    if (!pending) reset();
  }, [pending, reset]);
  if (!pending || !cancel) return null;
  const cancelling = mutation.isSuccess || operation?.startsWith("cancelling/");
  return (
    <div className="workflow-inline-actions">
      <Button
        variant="secondary"
        disabled={mutation.isPending || cancelling}
        onClick={() => mutation.mutate()}
      >
        {cancelling
          ? "Cancellation requested"
          : mutation.isPending
            ? "Cancelling…"
            : `Cancel ${label}`}
      </Button>
      {cancelling && (
        <p role="status" className="muted small">
          Stopping generation. An in-flight request may finish; completed stages
          are saved.
        </p>
      )}
      <ErrorNotice error={mutation.error} />
    </div>
  );
}
