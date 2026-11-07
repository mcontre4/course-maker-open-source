import type { LessonPlanResponse } from "../application/dto";
import { LessonFeasibilityNotice } from "./LessonFeasibilityNotice";

export function LessonOutlineSummary({
  plan,
  showFeasibility = true,
}: {
  plan: LessonPlanResponse;
  showFeasibility?: boolean;
}) {
  return (
    <>
      {showFeasibility && <LessonFeasibilityNotice plan={plan} />}
      <div className="outline-objectives">
        <p className="eyebrow">WHAT YOU’LL LEARN</p>
        <ul>
          {plan.objectives.map((objective) => (
            <li key={objective}>{objective}</li>
          ))}
        </ul>
      </div>
      <ol className="teaching-timeline">
        {plan.beats.map((beat, index) => (
          <li key={index}>
            <span className="beat-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <div className="beat-heading">
                <h3>{beat.title}</h3>
                <span>{beat.seconds}s</span>
              </div>
              <p>{beat.purpose}</p>
              <p className="muted teaching-notes">{beat.teachingNotes}</p>
              {beat.checkQuestion && (
                <details>
                  <summary>Check your understanding</summary>
                  <p>{beat.checkQuestion}</p>
                  <p className="muted">{beat.expectedAnswer}</p>
                </details>
              )}
            </div>
          </li>
        ))}
      </ol>
      {plan.examples.length > 0 && (
        <section className="lesson-examples">
          <p className="eyebrow">BRING IT TO LIFE</p>
          {plan.examples.map((example, index) => (
            <article key={index}>
              <h3>{example.problem}</h3>
              <ol>
                {example.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
              <p>{example.result}</p>
            </article>
          ))}
        </section>
      )}
      <details className="outline-details">
        <summary>Facts, scope & research sources</summary>
        <ul>
          {[
            ...plan.requiredFacts,
            ...plan.equations,
            ...plan.scopeBoundaries,
          ].map((fact, i) => (
            <li key={i}>{fact}</li>
          ))}
        </ul>
        <ul>
          {plan.sources.map((source, i) => (
            <li key={i}>
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.title} ↗
              </a>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}
