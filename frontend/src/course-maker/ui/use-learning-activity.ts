import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useApplication } from "./application-context";

const queryKey = ["learning-activity"];

export function useLearningActivity(enabled = true) {
  const log = useApplication().learningActivity;
  return useQuery({
    queryKey,
    enabled,
    queryFn: () => (log ? log.recent() : Promise.resolve([])),
  });
}

/** Remember the course or lesson once it has loaded. Failure never interrupts learning. */
export function useRecordOpened(itemId: string | undefined) {
  const log = useApplication().learningActivity;
  const cache = useQueryClient();
  useEffect(() => {
    if (!log || !itemId) return;
    log.record(itemId).then(
      () => void cache.invalidateQueries({ queryKey }),
      () => undefined,
    );
  }, [log, itemId, cache]);
}
