/** A lesson's own page, under which its interactives live. */
export type InteractiveHome = Readonly<{
  /** e.g. /lessons/lesson_1 or /courses/course_1/lessons/lesson_1 */
  lessonPath: string;
  /** Where "back to lesson" lands, showing the list of interactives. */
  backTo: string;
}>;

export function interactivePath(home: InteractiveHome, id: string) {
  return `${home.lessonPath}/interactives/${encodeURIComponent(id)}`;
}

export function standaloneInteractiveHome(lessonId: string): InteractiveHome {
  const lessonPath = `/lessons/${encodeURIComponent(lessonId)}`;
  return { lessonPath, backTo: `${lessonPath}?panel=interactives&edit=1` };
}

export function courseInteractiveHome(
  courseId: string,
  lessonId: string,
): InteractiveHome {
  const lessonPath = `/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lessonId)}`;
  return { lessonPath, backTo: `${lessonPath}?edit=1#lesson-interactives` };
}
