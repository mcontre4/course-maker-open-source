import { expect, it } from "vitest";
import { MemoryCourseBackend } from "../testing/course-backend";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import { searchContent } from "./content-search";

it("ranks exact and partial title matches ahead of description matches across content types", () => {
  const course = new MemoryCourseBackend().value;
  const courses = [
    {
      ...course,
      id: "description",
      title: "Programming",
      description: "Learn Python",
    },
    { ...course, id: "contained", title: "Learn Python" },
    { ...course, id: "prefix", title: "Python basics" },
    { ...course, id: "exact", title: "Python" },
  ];
  expect(
    searchContent("PYTHon", courses, []).map((match) => match.title),
  ).toEqual(["Python", "Python basics", "Learn Python", "Programming"]);
});

it("finds saved course lessons and standalone lessons from partial names", async () => {
  const course = new MemoryCourseBackend().value;
  const nested = course.chapters[0].lessons[0];
  const standalone = await new MemoryStandaloneBackend().create({
    title: "Café algebra",
    description: "Equations",
    minutes: 5,
  });
  const standaloneMatches = searchContent("  CAFE   ALG ", [], [standalone]);
  expect(standaloneMatches).toHaveLength(1);
  expect(standaloneMatches[0].href).toBe(`/lessons/${standalone.id}`);
  const nestedMatches = searchContent(nested.title, [course], []).filter(
    (match) => match.kind === "lesson",
  );
  expect(
    nestedMatches.some(
      (match) => match.href === `/courses/${course.id}/lessons/${nested.id}`,
    ),
  ).toBe(true);
  expect(searchContent("   ", [course], [standalone])).toEqual([]);
});

it("deduplicates owned and public content and preserves course lesson destinations", () => {
  const course = new MemoryCourseBackend().value;
  const nested = course.chapters[0].lessons[0];
  const publicLesson = {
    id: nested.id,
    title: nested.title,
    minutes: nested.minutes,
    image: nested.image,
    videoUrl: null,
    courseId: course.id,
  };
  const published = {
    courses: [{ ...course, lessons: [publicLesson] }],
    lessons: [publicLesson],
  };
  const owned = searchContent(nested.title, [course], [], published).filter(
    (match) => match.kind === "lesson",
  );
  expect(owned).toHaveLength(1);
  expect(owned[0].href).toBe(`/courses/${course.id}/lessons/${nested.id}`);
  const publicMatches = searchContent(nested.title, [], [], published).filter(
    (match) => match.kind === "lesson",
  );
  expect(publicMatches).toHaveLength(1);
  expect(publicMatches[0].href).toBe(
    `/watch/lessons/${nested.id}?course=${course.id}`,
  );
});
