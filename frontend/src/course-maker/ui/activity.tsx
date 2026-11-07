import { useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";

export function useActivity(
  kind: "course" | "lesson",
  id: string,
  thumbnail = false,
) {
  const cache = useQueryClient();
  return useSyncExternalStore(
    (notify) => cache.getQueryCache().subscribe(notify),
    () =>
      cache.getQueryData<{
        activeOperation?: string;
        thumbnailOperation?: string;
      }>([kind === "course" ? "courses" : "lessons", id])?.[
        thumbnail ? "thumbnailOperation" : "activeOperation"
      ] ?? "",
  );
}

export function ActivityNotice({
  operation,
  error,
}: {
  operation?: string;
  error?: string;
}) {
  if (!operation) return error ? <p role="alert">{error}</p> : null;
  const label = operation.includes("thumbnail")
    ? "Drawing your thumbnail"
    : operation.includes("style")
      ? "Planning your style"
      : operation.includes("syllabus")
        ? "Preparing your syllabus"
        : operation === "plan" || operation.includes("lessons/generate")
          ? "Preparing your lesson outline"
          : /video|storyboard|script\/generate|speech|animation/.test(operation)
            ? "Creating your lesson video"
            : "Saving your changes";
  return (
    <p role="status" className="generation-status">
      In Progress — {label}. You can refresh this page; it will update
      automatically.
    </p>
  );
}
