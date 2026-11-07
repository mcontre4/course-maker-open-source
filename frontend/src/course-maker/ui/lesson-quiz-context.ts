import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LessonQuiz } from "../application/lesson-quizzes";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { useApplication } from "./application-context";

const quizKey = (lessonId: string) => ["lesson-quiz", lessonId];

export function useLessonQuiz(lessonId: string) {
  const app = useApplication().quizzes;
  return useQuery({
    refetchInterval: (query) =>
      app?.serverGenerated && query.state.data === null ? 3000 : false,
    queryKey: quizKey(lessonId),
    queryFn: () => (app ? app.get.execute(lessonId) : Promise.resolve(null)),
    enabled: !!app,
  });
}

export function useQuizMutation<Input>(
  execute: (input: Input) => Promise<LessonQuiz>,
) {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: execute,
    onSuccess: (quiz) => cache.setQueryData(quizKey(quiz.lessonId), quiz),
  });
}

export function useGenerateQuiz(
  lesson: StandaloneLessonResponse,
  onlyIfMissing = false,
) {
  const application = useApplication();
  const app = application.quizzes;
  return useQuizMutation(async () => {
    if (!app) throw new Error("Quizzes are unavailable.");
    return app.generate.execute(
      lesson.content,
      application.generationPreferences?.get("lesson:" + lesson.id),
      onlyIfMissing,
    );
  });
}

/**
 * Drafts a quiz once, the first time `enabled` holds for a lesson that has
 * none, so there is always something to review rather than a blank page.
 */
export function useAutoQuiz(
  lesson: StandaloneLessonResponse,
  enabled: boolean,
) {
  const quiz = useLessonQuiz(lesson.id);
  const generate = useGenerateQuiz(lesson, true);
  const attempted = useRef(false);
  const ready =
    enabled && !!lesson.content.plan && quiz.isSuccess && quiz.data === null;
  const { mutate } = generate;
  useEffect(() => {
    if (!ready || attempted.current) return;
    attempted.current = true;
    mutate();
  }, [ready, mutate]);
}
