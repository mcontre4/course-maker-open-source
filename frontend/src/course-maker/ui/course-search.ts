import { courseTopics, subtopicPath, topicPath } from "./course-catalog";

export function searchResultsUrl(query: string) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  return `/explore?${params}`;
}

// Explore used to live on the home page as `/?q=…` and `/?topic=…`.
export function legacyExploreUrl(params: URLSearchParams) {
  const topic = params.get("topic");
  if (topic) {
    for (const item of courseTopics) {
      if (item.title === topic) return topicPath(item);
      if (item.subtopics.some((subtopic) => subtopic === topic))
        return subtopicPath(item, topic);
    }
  }
  const query = params.get("q");
  if (query?.trim()) return searchResultsUrl(query);
  return topic ? "/explore" : null;
}
