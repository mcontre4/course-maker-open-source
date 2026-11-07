import { createContext, useContext } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CourseApplication } from "../application/use-cases";

export const ApplicationContext = createContext<CourseApplication | null>(null);
export function useApplication(): CourseApplication {
  const application = useContext(ApplicationContext);
  if (!application)
    throw new Error("Course application has not been provided.");
  return application;
}
export function useCourses(enabled = true) {
  const app = useApplication();
  return useQuery({
    queryKey: ["courses"],
    enabled,
    queryFn: () => app.listCourses.execute(),
  });
}
export function useCourse(id: string) {
  const app = useApplication();
  return useQuery({
    queryKey: ["courses", id],
    queryFn: () => app.getCourse.execute(id),
    enabled: !!id,
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
}
export function useCourseMutation<Input, Output>(
  execute: (request: Input) => Promise<Output>,
) {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: execute,
    onSuccess: (result) => {
      if (
        result &&
        typeof result === "object" &&
        "id" in result &&
        "chapters" in result
      ) {
        cache.setQueryData(["courses", result.id], result);
      }
      void cache.invalidateQueries({ queryKey: ["credits"] });
      return cache.invalidateQueries({ queryKey: ["courses"] });
    },
    onError: () => {
      // Paid attempts may have been recorded even when content generation failed.
      void cache.invalidateQueries({ queryKey: ["courses"] });
      void cache.invalidateQueries({ queryKey: ["credits"] });
    },
  });
}
