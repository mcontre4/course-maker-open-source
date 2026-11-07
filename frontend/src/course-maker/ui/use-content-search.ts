import { useEffect, useMemo, useState } from "react";
import { useApplication, useCourses } from "./application-context";
import { searchContent } from "./content-search";
import { useLessons } from "./lesson-context";
import { useDiscovery } from "./use-discovery";
import { useOwnCreator } from "./CreatorLink";
import { useAuthentication } from "./authentication";
import { COURSE_CREATION_ENABLED } from "./feature-flags";

export function useContentSearch(value: string) {
  const query = value.trim().slice(0, 200);
  const [debounced, setDebounced] = useState(query);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query), 150);
    return () => window.clearTimeout(timer);
  }, [query]);
  const hasPublicSearch = !!useApplication().creators;
  const auth = useAuthentication();
  const privateSearch = !auth || !!auth.session?.user;
  const creator = useOwnCreator();
  const courses = useCourses(COURSE_CREATION_ENABLED && privateSearch);
  const lessons = useLessons(privateSearch);
  const published = useDiscovery(debounced, !!query && query === debounced);
  const currentPublic = query === debounced ? published.data : undefined;
  const creatorId = creator.data?.id;
  const matches = useMemo(
    () =>
      searchContent(
        query,
        (privateSearch && COURSE_CREATION_ENABLED
          ? (courses.data ?? [])
          : []
        ).filter((course) => !course.ownerId || course.ownerId === creatorId),
        privateSearch ? (lessons.data ?? []) : [],
        COURSE_CREATION_ENABLED || !currentPublic
          ? currentPublic
          : {
              courses: [],
              lessons: currentPublic.lessons.filter(
                (lesson) => !lesson.courseId,
              ),
            },
      ),
    [
      query,
      courses.data,
      lessons.data,
      currentPublic,
      creatorId,
      privateSearch,
    ],
  );
  const pending =
    !!query &&
    ((privateSearch && COURSE_CREATION_ENABLED && courses.isPending) ||
      (privateSearch &&
        COURSE_CREATION_ENABLED &&
        hasPublicSearch &&
        creator.isPending) ||
      (privateSearch && lessons.isPending) ||
      (hasPublicSearch && (query !== debounced || published.isPending)));
  const failed =
    (privateSearch && COURSE_CREATION_ENABLED && courses.isError) ||
    (privateSearch &&
      COURSE_CREATION_ENABLED &&
      hasPublicSearch &&
      creator.isError) ||
    (privateSearch && lessons.isError) ||
    (hasPublicSearch && query === debounced && published.isError);
  return {
    matches,
    pending,
    failed,
    retry: () => {
      if (privateSearch && COURSE_CREATION_ENABLED && courses.isError)
        void courses.refetch();
      if (privateSearch && COURSE_CREATION_ENABLED && creator.isError)
        void creator.refetch();
      if (privateSearch && lessons.isError) void lessons.refetch();
      if (published.isError) void published.refetch();
    },
  };
}
