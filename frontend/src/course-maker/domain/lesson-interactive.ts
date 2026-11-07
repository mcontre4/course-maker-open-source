/** One finished build. Only the current version's page travels with the interactive. */
export type InteractiveVersion = Readonly<{
  number: number;
  /** What the creator asked for: the first description, or a requested change. */
  request: string;
  createdAt: string;
}>;

export const interactiveBuildStages = [
  "reading_lesson",
  "designing",
  "building",
  "checking",
] as const;
export type InteractiveBuildStage = (typeof interactiveBuildStages)[number];

export type InteractiveBuild = Readonly<{
  request: string;
  stage: InteractiveBuildStage;
  startedAt: string;
}>;

export type InteractiveBuildFailure = Readonly<{
  request: string;
  message: string;
}>;

export type LessonInteractive = Readonly<{
  id: string;
  lessonId: string;
  brief: string;
  title: string;
  /** One line telling learners what they will figure out. */
  goal: string;
  /** "Try this" challenges shown next to the interactive. */
  prompts: readonly string[];
  versions: readonly InteractiveVersion[];
  /** The version the creator is previewing and changing. */
  currentVersion: number | null;
  html: string | null;
  /** The version learners get; null while it is not part of the lesson. */
  publishedVersion: number | null;
  publishedHtml: string | null;
  build: InteractiveBuild | null;
  failure: InteractiveBuildFailure | null;
  revision: number;
  createdAt: string;
  updatedAt: string;
}>;

/** What a learner receives: never drafts, build state or creator requests. */
export type LearnerInteractive = Readonly<{
  id: string;
  lessonId: string;
  version: number;
  title: string;
  goal: string;
  prompts: readonly string[];
  html: string;
}>;

export type InteractiveDetails = Readonly<{
  title: string;
  goal: string;
  prompts: readonly string[];
}>;

/** The parts of a lesson that ideas for an interactive are drawn from. */
export type InteractiveLessonContext = Readonly<{
  lessonId: string;
  title: string;
  topics: readonly string[];
}>;

export const interactiveLimits = {
  perLesson: 10,
  brief: 2000,
  change: 1000,
  title: 80,
  goal: 200,
  prompts: 6,
  prompt: 160,
} as const;

export type InteractiveState =
  "building" | "failed" | "draft" | "live" | "live_with_changes";

export function interactiveState(
  interactive: LessonInteractive,
): InteractiveState {
  if (interactive.build) return "building";
  if (interactive.failure && interactive.currentVersion === null)
    return "failed";
  if (interactive.publishedVersion === null) return "draft";
  return interactive.publishedVersion === interactive.currentVersion
    ? "live"
    : "live_with_changes";
}

export function learnerView(
  interactive: LessonInteractive,
): LearnerInteractive | null {
  if (interactive.publishedVersion === null || !interactive.publishedHtml)
    return null;
  return {
    id: interactive.id,
    lessonId: interactive.lessonId,
    version: interactive.publishedVersion,
    title: interactive.title,
    goal: interactive.goal,
    prompts: interactive.prompts,
    html: interactive.publishedHtml,
  };
}

/** The first problem with a description, in words a creator can act on, or null. */
export function briefProblem(brief: string): string | null {
  const text = brief.trim();
  if (!text) return "Describe what learners should be able to do.";
  if (text.length > interactiveLimits.brief)
    return `Keep the description under ${interactiveLimits.brief} characters.`;
  return null;
}

export function changeProblem(change: string): string | null {
  const text = change.trim();
  if (!text) return "Describe the change you want.";
  if (text.length > interactiveLimits.change)
    return `Keep the change under ${interactiveLimits.change} characters.`;
  return null;
}

export function detailsProblem(details: InteractiveDetails): string | null {
  const title = details.title.trim();
  if (!title) return "Give the interactive a title.";
  if (title.length > interactiveLimits.title)
    return `Keep the title under ${interactiveLimits.title} characters.`;
  if (details.goal.trim().length > interactiveLimits.goal)
    return `Keep the goal under ${interactiveLimits.goal} characters.`;
  if (details.prompts.length > interactiveLimits.prompts)
    return `Use up to ${interactiveLimits.prompts} challenges.`;
  if (details.prompts.some((prompt) => !prompt.trim()))
    return "Fill in or remove empty challenges.";
  if (
    details.prompts.some((prompt) => prompt.length > interactiveLimits.prompt)
  )
    return `Keep each challenge under ${interactiveLimits.prompt} characters.`;
  return null;
}

export function tidyDetails(details: InteractiveDetails): InteractiveDetails {
  return {
    title: details.title.trim(),
    goal: details.goal.trim(),
    prompts: details.prompts.map((prompt) => prompt.trim()),
  };
}

/** Starting points drawn from what the lesson teaches, so nobody faces a blank box. */
export function interactiveIdeas(
  lesson: Pick<InteractiveLessonContext, "title" | "topics">,
): readonly string[] {
  const subjects = [
    ...lesson.topics.map((topic) => topic.trim()).filter(Boolean),
    lesson.title.trim(),
  ].filter(Boolean);
  if (!subjects.length) return [];
  const pick = (index: number) => subjects[index % subjects.length];
  return [
    `A simulation for “${pick(0)}”: learners change the settings and watch what happens.`,
    `A step-by-step walkthrough of “${pick(1)}” that learners can pause, replay and explore.`,
    `A hands-on challenge on “${pick(2)}”: learners adjust things until they reach a target.`,
  ];
}

export class LessonInteractiveError extends Error {}
