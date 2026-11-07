import { describe, expect, it } from "vitest";
import type { PublishedLesson } from "../application/creators";
import { courseTopics } from "./course-catalog";
import { lessonsInTopic, lessonsWithoutTopic } from "./explore-courses";

function lesson(id: string, title: string): PublishedLesson {
  return {
    id,
    title,
    minutes: 5,
    image: "story",
    videoUrl: null,
    courseId: null,
  };
}

const lessons = [
  lesson("a", "Sorting algorithms, visualised"),
  lesson("b", "How neural networks learn"),
  lesson("c", "Machine learning from scratch"),
  lesson("d", "The story of the printing press"),
];
const aiTopic = courseTopics.find((topic) => topic.slug === "ai-data-science")!;
const csTopic = courseTopics.find(
  (topic) => topic.slug === "computer-science",
)!;

describe("lessons by topic", () => {
  it("files lessons under a topic by their title", () => {
    expect(lessonsInTopic(lessons, csTopic).map((item) => item.id)).toEqual([
      "a",
    ]);
    expect(lessonsInTopic(lessons, aiTopic).map((item) => item.id)).toEqual([
      "b",
      "c",
    ]);
  });

  it("narrows a topic to one subtopic", () => {
    expect(
      lessonsInTopic(lessons, aiTopic, "Machine learning").map(
        (item) => item.id,
      ),
    ).toEqual(["b", "c"]);
    expect(lessonsInTopic(lessons, aiTopic, "Data analysis")).toEqual([]);
  });

  it("lists lessons that match no topic", () => {
    expect(lessonsWithoutTopic(lessons).map((item) => item.id)).toEqual(["d"]);
  });
});
