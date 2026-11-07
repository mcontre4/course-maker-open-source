import type { LessonPlanResponse } from "../application/dto";

export function LessonFeasibilityNotice({
  plan,
}: {
  plan: LessonPlanResponse;
}) {
  if (plan.feasibilityStatus !== "infeasible") return null;
  return (
    <section className="outline-objectives" role="status">
      <h3>This lesson needs a scope or duration change</h3>
      <p>{plan.feasibilityExplanation}</p>
      {plan.recommendedVideoMinutes != null && (
        <p>
          Recommended minimum: {plan.recommendedVideoMinutes} video minutes.
        </p>
      )}
      {plan.recommendedScopeAdjustment && (
        <p>{plan.recommendedScopeAdjustment}</p>
      )}
    </section>
  );
}
