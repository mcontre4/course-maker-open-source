import type { LessonPlanResponse } from "../application/dto";
import { MAX_LESSON_MINUTES } from "../application/standalone-lessons";
import { Button } from "./primitives/Button";

export function LessonTimeFix({
  plan,
  minutes,
  disabled,
  pending,
  error,
  onExtend,
  onTrim,
  onAskGuide,
}: {
  plan: LessonPlanResponse;
  minutes: number;
  disabled: boolean;
  pending: boolean;
  error: Error | null;
  onExtend: (minutes: number) => void;
  onTrim: () => void;
  onAskGuide: () => void;
}) {
  const needed =
    plan.recommendedVideoMinutes ??
    Math.ceil(plan.beats.reduce((sum, beat) => sum + beat.seconds, 0) / 60);
  const canExtend = needed > minutes && needed <= MAX_LESSON_MINUTES;
  const scale = Math.max(needed, minutes, 1);
  return (
    <section className="time-fix" aria-labelledby="time-fix-title">
      <div className="time-fix-summary">
        <p className="eyebrow">ONE QUICK FIX BEFORE YOUR VIDEO</p>
        <h2 id="time-fix-title">
          This topic won’t fit in {minutes}{" "}
          {minutes === 1 ? "minute" : "minutes"}
        </h2>
        {plan.feasibilityExplanation && <p>{plan.feasibilityExplanation}</p>}
        <div className="time-fix-meter" aria-hidden="true">
          <div>
            <span>You asked for</span>
            <i style={{ width: `${(minutes / scale) * 100}%` }} />
            <b>{minutes} min</b>
          </div>
          <div data-over="true">
            <span>It needs about</span>
            <i style={{ width: `${(needed / scale) * 100}%` }} />
            <b>{needed} min</b>
          </div>
        </div>
      </div>
      <div
        className="time-fix-options"
        role="group"
        aria-label="Ways to fix it"
      >
        {canExtend ? (
          <article>
            <h3>Give it more time</h3>
            <p>
              Keep every idea and make the lesson {needed} minutes. We’ll
              rebuild your outline to match.
            </p>
            <Button disabled={disabled} onClick={() => onExtend(needed)}>
              Make it {needed} minutes
            </Button>
          </article>
        ) : (
          <article data-unavailable="true">
            <h3>Give it more time</h3>
            <p>
              Lessons can run up to {MAX_LESSON_MINUTES} minutes, and this topic
              needs about {needed}. Narrowing it is the way to go.
            </p>
          </article>
        )}
        <article>
          <h3>Narrow the topic</h3>
          <p>
            {plan.recommendedScopeAdjustment ||
              "We’ll cut the least essential parts and keep the core idea."}
          </p>
          <Button
            variant={canExtend ? "secondary" : "primary"}
            disabled={disabled}
            onClick={onTrim}
          >
            Trim it to {minutes} {minutes === 1 ? "minute" : "minutes"}
          </Button>
        </article>
        <article>
          <h3>Choose what stays</h3>
          <p>
            Tell your lesson guide what matters most and it will rewrite the
            outline around that.
          </p>
          <Button variant="secondary" disabled={disabled} onClick={onAskGuide}>
            Open the guide
          </Button>
        </article>
      </div>
      {pending && (
        <p className="time-fix-status" role="status">
          <span className="loading-spinner" aria-hidden="true" />
          Rebuilding your outline…
        </p>
      )}
      {error && (
        <p className="time-fix-status" role="alert" data-error="true">
          {error.message}
        </p>
      )}
    </section>
  );
}
