import { Link } from "react-router-dom";
import type { CourseResponse } from "../../application/dto";
import { Progress, Thumbnail } from "../components";
import { SpendDetails } from "../SpendDetails";

export function LessonNavigation({
  course,
  selected,
}: {
  course: CourseResponse;
  selected: string;
}) {
  const lessons = course.chapters.flatMap((c) => c.lessons);
  return (
    <aside
      className="panel lesson-navigation"
      aria-label="Course chapters and lessons"
    >
      <h2>Your learning path</h2>
      <p className="progress-label">
        {course.completed.length} of {lessons.length} lessons complete ·{" "}
        {Math.round((course.completed.length / lessons.length) * 100)}%
      </p>
      <Progress completed={course.completed.length} total={lessons.length} />
      <div className="spend-group">
        <SpendDetails course={course} lessonId={selected} />
        <SpendDetails course={course} />
      </div>
      <p className="eyebrow muted">CHAPTERS & LESSONS</p>
      <div className="lesson-list">
        {course.chapters.map((chapter, c) => (
          <section key={chapter.id}>
            <div className="chapter-heading">
              <Thumbnail name={chapter.image} variant="chapter" />
              <div>
                <p className="eyebrow">CHAPTER {c + 1}</p>
                <h3>{chapter.title}</h3>
              </div>
            </div>
            <ol>
              {chapter.lessons.map((lesson) => (
                <li key={lesson.id}>
                  <Link
                    to={"/courses/" + course.id + "/lessons/" + lesson.id}
                    className={lesson.id === selected ? "selected" : ""}
                    aria-current={lesson.id === selected ? "page" : undefined}
                  >
                    <Thumbnail name={lesson.image} />
                    <span>
                      <strong>{lesson.title}</strong>
                      <small>
                        {course.completed.includes(lesson.id)
                          ? "✓ Complete"
                          : lesson.id === selected
                            ? "Current lesson"
                            : lesson.minutes + " min · Not started"}
                      </small>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
      <Link className="small" to={"/courses/" + course.id + "/syllabus"}>
        View full syllabus →
      </Link>
    </aside>
  );
}
