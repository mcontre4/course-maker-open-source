export type Duration =
  | Readonly<{ mode: "total"; hours: number }>
  | Readonly<{ mode: "weekly"; weeks: number; hoursPerWeek: number }>;

export type CourseDetails = Readonly<{
  title: string;
  description: string;
  duration: Duration;
}>;
export type Question = Readonly<{
  id: string;
  prompt: string;
  options: readonly string[];
  answer: number;
  explanation: string;
}>;
export type Lesson = Readonly<{
  id: string;
  title: string;
  image: string;
  topics: readonly string[];
  minutes: number;
  videoUrl: string | null;
  quiz: readonly Question[];
}>;
export type Chapter = Readonly<{
  id: string;
  title: string;
  summary: string;
  image: string;
  lessons: readonly Lesson[];
}>;
export type Message = Readonly<{ role: "guide" | "learner"; text: string }>;
export type Course = CourseDetails &
  Readonly<{
    id: string;
    image: string;
    status: "draft" | "ready";
    chapters: readonly Chapter[];
    reviewed: readonly string[];
    completed: readonly string[];
    messages: readonly Message[];
  }>;

export class CourseError extends Error {}

export function totalHours(duration: Duration): number {
  if (duration.mode === "total") {
    if (
      !Number.isFinite(duration.hours) ||
      duration.hours < 1 ||
      duration.hours > 480
    )
      throw new CourseError("Choose between 1 and 480 total hours.");
    return duration.hours;
  }
  if (
    !Number.isInteger(duration.weeks) ||
    duration.weeks < 1 ||
    duration.weeks > 12
  )
    throw new CourseError("Choose between 1 and 12 weeks.");
  if (
    !Number.isFinite(duration.hoursPerWeek) ||
    duration.hoursPerWeek < 1 ||
    duration.hoursPerWeek > 40
  )
    throw new CourseError("Choose between 1 and 40 hours per week.");
  return duration.weeks * duration.hoursPerWeek;
}

export function validateDetails(details: CourseDetails): void {
  if (!details.title.trim() || details.title.trim().length > 120)
    throw new CourseError("Give your course a title of up to 120 characters.");
  if (!details.description.trim() || details.description.trim().length > 2000)
    throw new CourseError(
      "Describe your learning goal in up to 2,000 characters.",
    );
  totalHours(details.duration);
}

export const lessonsOf = (course: Course): readonly Lesson[] =>
  course.chapters.flatMap((c) => c.lessons);

export function requireLesson(course: Course, lessonId: string): Lesson {
  const lesson = lessonsOf(course).find((l) => l.id === lessonId);
  if (!lesson) throw new CourseError("This lesson could not be found.");
  if (course.status !== "ready")
    throw new CourseError("Approve the syllabus before starting a lesson.");
  return lesson;
}

export function approve(course: Course): Course {
  validateSyllabus(course.chapters);
  return { ...course, status: "ready" };
}

export function markReviewed(course: Course, lessonId: string): Course {
  const lesson = requireLesson(course, lessonId);
  if (!lesson.videoUrl)
    throw new CourseError("This lesson’s video is not ready yet.");
  return { ...course, reviewed: [...new Set([...course.reviewed, lessonId])] };
}

export function editTopic(
  course: Course,
  lessonId: string,
  topic: string,
  operation: "add" | "remove",
): Course {
  if (course.status !== "draft")
    throw new CourseError("Only draft syllabuses can be edited.");
  if (!topic.trim() || topic.length > 200)
    throw new CourseError("Use a topic between 1 and 200 characters.");
  let found = false;
  const chapters = course.chapters.map((chapter) => ({
    ...chapter,
    lessons: chapter.lessons.map((lesson) => {
      if (lesson.id !== lessonId) return lesson;
      found = true;
      const topics =
        operation === "add"
          ? [...new Set([...lesson.topics, topic.trim()])]
          : lesson.topics.filter((t) => t !== topic);
      if (!topics.length)
        throw new CourseError("Keep at least one topic in each lesson.");
      return { ...lesson, topics };
    }),
  }));
  if (!found) throw new CourseError("This lesson could not be found.");
  return { ...course, chapters };
}

export function gradeQuiz(
  course: Course,
  lessonId: string,
  answers: readonly number[],
) {
  const lesson = requireLesson(course, lessonId);
  if (!lesson.videoUrl)
    throw new CourseError("This lesson’s video is not ready yet.");
  if (!course.reviewed.includes(lessonId))
    throw new CourseError("Watch the lesson video before taking its quiz.");
  validateQuiz(lesson.quiz);
  if (
    answers.length !== lesson.quiz.length ||
    lesson.quiz.some(
      (question, i) =>
        !Number.isInteger(answers[i]) ||
        answers[i] < 0 ||
        answers[i] >= question.options.length,
    )
  )
    throw new CourseError("Answer every question before checking your quiz.");
  const score = lesson.quiz.filter((q, i) => q.answer === answers[i]).length;
  const passed = score === lesson.quiz.length;
  return {
    course: {
      ...course,
      completed: passed
        ? [...new Set([...course.completed, lessonId])]
        : course.completed,
    },
    result: {
      score,
      total: lesson.quiz.length,
      passed,
      feedback: lesson.quiz.map((q, i) => ({
        correct: q.answer === answers[i],
        explanation: q.explanation,
      })),
    },
  };
}

export function validateQuiz(questions: readonly Question[]): void {
  if (!questions.length)
    throw new CourseError("This lesson’s quiz is not ready yet.");
  const ids = new Set<string>();
  for (const question of questions) {
    if (
      !question.id ||
      ids.has(question.id) ||
      !question.prompt.trim() ||
      question.options.length < 2 ||
      question.options.some((option) => !option.trim()) ||
      !Number.isInteger(question.answer) ||
      question.answer < 0 ||
      question.answer >= question.options.length
    )
      throw new CourseError("This lesson’s quiz is invalid.");
    ids.add(question.id);
  }
}

export function validateSyllabus(chapters: readonly Chapter[]): void {
  if (!chapters.length)
    throw new CourseError("A course needs at least one chapter.");
  const chapterIds = new Set<string>();
  const lessonIds = new Set<string>();
  for (const chapter of chapters) {
    if (
      !chapter.id ||
      chapterIds.has(chapter.id) ||
      !chapter.title.trim() ||
      !chapter.lessons.length
    )
      throw new CourseError(
        "Every chapter needs a unique ID, a title, and at least one lesson.",
      );
    chapterIds.add(chapter.id);
    for (const lesson of chapter.lessons) {
      if (
        !lesson.id ||
        lessonIds.has(lesson.id) ||
        !lesson.title.trim() ||
        !Number.isFinite(lesson.minutes) ||
        lesson.minutes <= 0 ||
        !lesson.topics.length ||
        lesson.topics.some((topic) => !topic.trim() || topic.length > 200)
      )
        throw new CourseError(
          "Every lesson needs a unique ID, a title, a positive duration, and valid topics.",
        );
      lessonIds.add(lesson.id);
      validateQuiz(lesson.quiz);
    }
  }
}

export function validateCourse(course: Course): void {
  validateDetails(course);
  if (course.status === "ready" || course.chapters.length)
    validateSyllabus(course.chapters);
  const lessonIds = new Set(lessonsOf(course).map((lesson) => lesson.id));
  if (
    !course.id ||
    [...course.reviewed, ...course.completed].some(
      (id) => !lessonIds.has(id),
    ) ||
    new Set(course.reviewed).size !== course.reviewed.length ||
    new Set(course.completed).size !== course.completed.length ||
    course.completed.some((id) => !course.reviewed.includes(id)) ||
    (course.status === "draft" &&
      (course.reviewed.length > 0 || course.completed.length > 0))
  )
    throw new CourseError("Course progress is invalid.");
}
