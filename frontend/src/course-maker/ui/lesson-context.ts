import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApplication } from "./application-context";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";

export function useLessons(enabled = true) {
  const app = useApplication().lessons;
  return useQuery({
    queryKey: ["lessons"],
    enabled,
    queryFn: () => (app ? app.list.execute() : Promise.resolve([])),
  });
}
export function useStandaloneLesson(id: string) {
  const app = useApplication().lessons;
  return useQuery({
    queryKey: ["lessons", id],
    queryFn: () => {
      if (!app)
        throw new Error("Standalone lessons require a server connection.");
      return app.get.execute(id);
    },
    enabled: !!id,
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
}
export function useLessonMutation<Input>(
  execute: (input: Input) => Promise<StandaloneLessonResponse>,
) {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: execute,
    onSuccess: (lesson) => {
      cache.setQueryData(["lessons", lesson.id], lesson);
      void cache.invalidateQueries({ queryKey: ["lessons"], exact: true });
      void cache.invalidateQueries({ queryKey: ["credits"] });
    },
    onError: () => {
      void cache.invalidateQueries({ queryKey: ["lessons"] });
      void cache.invalidateQueries({ queryKey: ["credits"] });
    },
  });
}
