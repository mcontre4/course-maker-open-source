import { Link } from "react-router-dom";
import type { LessonFlow } from "../application/lesson-flow";

export function LessonSteps({
  active,
  lessonId,
  disabled = false,
  flow = "guided",
}: {
  active: "details" | "review" | "video";
  lessonId?: string;
  disabled?: boolean;
  flow?: LessonFlow;
}) {
  const steps = [
    {
      id: "details",
      label: "Details",
      hint: "Topic, audience & length",
      to: lessonId ? `/lessons/${lessonId}/edit` : "/lessons/new",
    },
    {
      id: "review",
      label: "Review",
      hint:
        flow === "automatic"
          ? "Skipped · done for you"
          : "Check the outline & script",
      to: `/lessons/${lessonId}?step=review&edit=1`,
    },
    {
      id: "video",
      label: "Video",
      hint: "Create, watch & edit",
      to: `/lessons/${lessonId}?step=video`,
    },
  ] as const;
  const activeIndex = steps.findIndex((step) => step.id === active);
  return (
    <nav className="lesson-steps" aria-label="Lesson creation steps">
      <ol>
        {steps.map((step, index) => {
          const state =
            index < activeIndex
              ? "done"
              : index === activeIndex
                ? "current"
                : "upcoming";
          const content = (
            <>
              <b aria-hidden="true">
                {flow === "automatic" && step.id === "review"
                  ? "–"
                  : state === "done"
                    ? "✓"
                    : index + 1}
              </b>
              <span className="lesson-step-copy">
                <span>{step.label}</span>
                <small>{step.hint}</small>
              </span>
            </>
          );
          return (
            <li
              key={step.id}
              data-state={state}
              data-skipped={
                flow === "automatic" && step.id === "review" ? "" : undefined
              }
            >
              {disabled || !lessonId || active === step.id ? (
                <span
                  className="lesson-step"
                  aria-current={active === step.id ? "step" : undefined}
                >
                  {content}
                </span>
              ) : (
                <Link
                  className="lesson-step"
                  to={step.to}
                  aria-label={`${index + 1} ${step.label}`}
                >
                  {content}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
