import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LessonInteractive } from "../application/lesson-interactives";
import { useApplication } from "./application-context";

const listKey = (lessonId: string) => ["lesson-interactives", lessonId];
const itemKey = (lessonId: string, id: string) => [
  "lesson-interactives",
  lessonId,
  id,
];
const buildPollMilliseconds = 1500;

export function useLessonInteractives(lessonId: string) {
  const app = useApplication().interactives;
  return useQuery({
    queryKey: listKey(lessonId),
    queryFn: () => (app ? app.list(lessonId) : Promise.resolve([])),
    enabled: !!app && !!lessonId,
    refetchInterval: (query) =>
      query.state.data?.some((item) => item.build)
        ? buildPollMilliseconds
        : false,
  });
}

export function useLessonInteractive(lessonId: string, id: string) {
  const app = useApplication().interactives;
  return useQuery({
    queryKey: itemKey(lessonId, id),
    queryFn: () => app!.get({ lessonId, id }),
    enabled: !!app && !!id,
    refetchInterval: (query) =>
      query.state.data?.build ? buildPollMilliseconds : false,
  });
}

/** Any change to one interactive shows up in its page and in the lesson's list. */
export function useInteractiveMutation<Input>(
  execute: (input: Input) => Promise<LessonInteractive>,
) {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: execute,
    onSuccess: async (item) => {
      cache.setQueryData(itemKey(item.lessonId, item.id), item);
      await cache.invalidateQueries({
        queryKey: listKey(item.lessonId),
        exact: true,
      });
      await cache.invalidateQueries({
        queryKey: learnerKey(item.lessonId),
        exact: true,
      });
    },
  });
}

export function useRemoveInteractive(lessonId: string) {
  const app = useApplication().interactives;
  const cache = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => {
      if (!app) throw new Error("Interactives are unavailable.");
      return app.remove({ lessonId, id });
    },
    // The studio is still on screen here, so its own query is left to expire.
    onSuccess: async () => {
      await cache.invalidateQueries({
        queryKey: listKey(lessonId),
        exact: true,
      });
      await cache.invalidateQueries({
        queryKey: learnerKey(lessonId),
        exact: true,
      });
    },
  });
}

export function useReorderInteractives(lessonId: string) {
  const app = useApplication().interactives;
  const cache = useQueryClient();
  return useMutation({
    mutationFn: (orderedIds: readonly string[]) => {
      if (!app) throw new Error("Interactives are unavailable.");
      return app.reorder(lessonId, orderedIds);
    },
    onSuccess: async (items) => {
      cache.setQueryData(listKey(lessonId), items);
      await cache.invalidateQueries({
        queryKey: learnerKey(lessonId),
        exact: true,
      });
    },
  });
}

const learnerKey = (lessonId: string) => ["learner-interactives", lessonId];

export function useLearnerInteractives(lessonId: string) {
  const app = useApplication().learnerInteractives;
  return useQuery({
    queryKey: learnerKey(lessonId),
    queryFn: () => (app ? app.list(lessonId) : Promise.resolve([])),
    enabled: !!app && !!lessonId,
  });
}
