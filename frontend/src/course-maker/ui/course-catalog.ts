export const courseTopics = [
  {
    slug: "computer-science",
    title: "Computer science",
    blurb:
      "Learn to write code, design algorithms, and build things for the web.",
    symbol: "{ }",
    color: "lavender",
    subtopics: ["Programming", "Algorithms", "Web development"],
  },
  {
    slug: "ai-data-science",
    title: "AI & data science",
    blurb:
      "Understand how machines learn, and turn raw data into clear answers.",
    symbol: "✳",
    color: "apricot",
    subtopics: ["Artificial intelligence", "Machine learning", "Data analysis"],
  },
  {
    slug: "engineering",
    title: "Engineering",
    blurb:
      "Explore how energy, circuits, and machines work, then build your own.",
    symbol: "Q → W",
    color: "sage",
    subtopics: ["Thermodynamics", "Electrical engineering", "Robotics"],
  },
  {
    slug: "mathematics",
    title: "Mathematics",
    blurb:
      "Build intuition for vectors, change, and chance with visual examples.",
    symbol: "∑",
    color: "lavender",
    subtopics: ["Linear algebra", "Calculus", "Probability & statistics"],
  },
] as const;

export type CourseTopic = (typeof courseTopics)[number];

export const recommendedCourses = [
  {
    id: "python",
    title: "Python for curious minds",
    topic: "Computer science",
    subtopics: ["Programming", "Algorithms"],
    description:
      "Write your first programs and solve everyday problems, one small project at a time.",
    hours: 6,
    lessons: 18,
    level: "Beginner",
    symbol: "{ }",
    color: "sage",
  },
  {
    id: "web",
    title: "Build your first website",
    topic: "Computer science",
    subtopics: ["Web development", "Programming"],
    description:
      "Bring an idea to the browser with HTML, CSS, and a little JavaScript.",
    hours: 8,
    lessons: 24,
    level: "Beginner",
    symbol: "</>",
    color: "lavender",
  },
  {
    id: "ml",
    title: "Machine learning, made simple",
    topic: "AI & data science",
    subtopics: ["Machine learning", "Artificial intelligence"],
    description:
      "Discover how models learn from data, then train and evaluate your own.",
    hours: 10,
    lessons: 28,
    level: "Beginner",
    symbol: "✳",
    color: "apricot",
  },
  {
    id: "data",
    title: "Tell a story with data",
    topic: "AI & data science",
    subtopics: ["Data analysis"],
    description:
      "Turn a messy dataset into clear charts, useful patterns, and better questions.",
    hours: 5,
    lessons: 15,
    level: "Beginner",
    symbol: "▥",
    color: "sage",
  },
  {
    id: "thermo",
    title: "Thermodynamics in everyday life",
    topic: "Engineering",
    subtopics: ["Thermodynamics"],
    description:
      "Explore heat, energy, and entropy through engines, refrigerators, and the world around you.",
    hours: 7,
    lessons: 21,
    level: "Beginner",
    symbol: "Q → W",
    color: "apricot",
  },
  {
    id: "robotics",
    title: "Circuits to robots",
    topic: "Engineering",
    subtopics: ["Electrical engineering", "Robotics"],
    description:
      "Connect circuits, sensors, and motors to understand how robots sense and move.",
    hours: 9,
    lessons: 24,
    level: "Intermediate",
    symbol: "+ −",
    color: "lavender",
  },
  {
    id: "algebra",
    title: "The language of vectors",
    topic: "Mathematics",
    subtopics: ["Linear algebra", "Calculus"],
    description:
      "Build intuition for vectors, matrices, and changing quantities with visual examples.",
    hours: 6,
    lessons: 18,
    level: "Beginner",
    symbol: "∑",
    color: "lavender",
  },
  {
    id: "probability",
    title: "Making sense of uncertainty",
    topic: "Mathematics",
    subtopics: ["Probability & statistics"],
    description:
      "Use probability and statistics to reason about chance and make informed decisions.",
    hours: 5,
    lessons: 16,
    level: "Beginner",
    symbol: "P(A)",
    color: "sage",
  },
] as const;

export function matchesCourseSearch(search: string, fields: readonly string[]) {
  const text = fields.join(" ").toLocaleLowerCase();
  return search
    .trim()
    .toLocaleLowerCase()
    .split(/\s+/)
    .every((word) => text.includes(word));
}

export function topicBySlug(slug: string | undefined) {
  return courseTopics.find((topic) => topic.slug === slug);
}

export function topicPath(topic: CourseTopic) {
  return `/explore/${topic.slug}`;
}

export function subtopicPath(topic: CourseTopic, subtopic: string) {
  return `${topicPath(topic)}?${new URLSearchParams({ sub: subtopic })}`;
}

// Published courses carry no topic of their own, so a course belongs to a
// topic when its text mentions one of the topic's words.
const subtopicWords: Record<string, readonly string[]> = {
  Programming: ["programming", "coding", "code", "python", "software"],
  Algorithms: ["algorithm", "sorting", "recursion", "data structure"],
  "Web development": ["web", "website", "html", "css", "javascript"],
  "Artificial intelligence": [
    "artificial intelligence",
    "ai",
    "neural network",
    "chatbot",
  ],
  "Machine learning": ["machine learning", "deep learning", "neural network"],
  "Data analysis": ["data", "dataset", "analytics", "visualization"],
  Thermodynamics: ["thermodynamic", "heat", "entropy", "temperature"],
  "Electrical engineering": ["circuit", "electrical", "voltage", "electronics"],
  Robotics: ["robot", "sensor", "motor"],
  "Linear algebra": ["linear algebra", "vector", "matrix", "matrices"],
  Calculus: ["calculus", "derivative"],
  "Probability & statistics": [
    "probability",
    "statistics",
    "statistical",
    "probability & statistics",
  ],
};

function mentions(text: string, word: string) {
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${escaped}(s|es)?([^a-z0-9]|$)`, "i").test(
    text,
  );
}

export function textInSubtopic(text: string, subtopic: string) {
  return [subtopic, ...(subtopicWords[subtopic] ?? [])].some((word) =>
    mentions(text, word),
  );
}

export function textInTopic(text: string, topic: CourseTopic) {
  return topic.subtopics.some((subtopic) => textInSubtopic(text, subtopic));
}
