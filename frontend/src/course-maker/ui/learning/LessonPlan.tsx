import { CancelGenerationButton } from "../CancelGenerationButton";
import { useActivity } from "../activity";
import { useEffect } from "react";
import type { GenerationMode } from "../../application/generation-mode";
import type { LessonResponse } from "../../application/dto";
import { useApplication, useCourseMutation } from "../application-context";
import { ErrorNotice } from "../components";
import { QualitySettings } from "../GenerationModeSelector";
import { useGenerationMode } from "../generation-mode";
import { Button } from "../primitives/Button";
import { LessonFeasibilityNotice } from "../LessonFeasibilityNotice";

export function LessonPlan({
  courseId,
  lesson,
  disabled = false,
  onBusyChange,
  mode,
  onModeChange,
}: {
  courseId: string;
  lesson: LessonResponse;
  disabled?: boolean;
  onBusyChange?(busy: boolean): void;
  mode?: GenerationMode;
  onModeChange?(mode: GenerationMode): void;
}) {
  const app = useApplication();
  const [storedMode, setStoredMode] = useGenerationMode(
    "course-lesson:" + courseId + ":" + lesson.id,
    "course:" + courseId,
  );
  const generationMode = mode ?? storedMode;
  const setGenerationMode = onModeChange ?? setStoredMode;
  const activeOperation = useActivity("course", courseId);
  const generation = useCourseMutation(async () => {
    if (!app.generateLesson)
      throw new Error("Lesson generation requires API mode.");
    return app.generateLesson.execute({
      courseId,
      lessonId: lesson.id,
      generationMode,
    });
  });
  const pending =
    generation.isPending || activeOperation === "lessons/generate";
  useEffect(() => {
    onBusyChange?.(pending);
    return () => onBusyChange?.(false);
  }, [pending, onBusyChange]);
  const plan = lesson.plan;
  return (
    <section
      className="panel lesson-coverage lesson-plan"
      aria-label="Lesson teaching plan"
    >
      <h2>
        {plan ? "Your lesson plan" : "Create this lesson’s teaching plan"}
      </h2>
      {!plan && (
        <>
          <p>
            Research the topic and build a teaching progression with worked
            examples and checks for understanding.
          </p>
          <QualitySettings
            value={generationMode}
            onChange={setGenerationMode}
            disabled={pending || disabled}
          />
          <Button
            disabled={pending || disabled || !app.generateLesson}
            onClick={() => generation.mutate()}
          >
            {pending ? "Researching and planning…" : "Generate lesson plan"}
          </Button>
          {pending && (
            <p role="status">
              This can take a few minutes. Your plan will be saved when it is
              ready.
            </p>
          )}
        </>
      )}
      <CancelGenerationButton
        kind="course"
        id={courseId}
        pending={pending}
        operation={activeOperation}
        label="outline generation"
      />
      <ErrorNotice error={generation.error} />
      {plan && (
        <>
          <LessonFeasibilityNotice plan={plan} />
          <h3>Learning objectives</h3>
          <ul>
            {plan.objectives.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h3>Assumed knowledge</h3>
          <ul>
            {plan.assumedKnowledge.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h3>New knowledge</h3>
          <ul>
            {plan.introducedKnowledge.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h3>Teaching progression</h3>
          <ol>
            {plan.beats.map((beat, index) => (
              <li key={index}>
                <h4>
                  {beat.title} · {beat.seconds} seconds
                </h4>
                <p>{beat.purpose}</p>
                <p>{beat.teachingNotes}</p>
                {beat.checkQuestion && (
                  <details>
                    <summary>{beat.checkQuestion}</summary>
                    <p>{beat.expectedAnswer}</p>
                  </details>
                )}
              </li>
            ))}
          </ol>
          <h3>Required facts</h3>
          <ul>
            {plan.requiredFacts.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          {plan.equations.length > 0 && (
            <>
              <h3>Equations</h3>
              <ul>
                {plan.equations.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </>
          )}
          <h3>Illustrative examples</h3>
          {plan.examples.map((e, i) => (
            <article key={i}>
              <h4>{e.problem}</h4>
              <ol>
                {e.steps.map((t, j) => (
                  <li key={j}>{t}</li>
                ))}
              </ol>
              <p>{e.result}</p>
            </article>
          ))}
          <h3>Misconceptions and corrections</h3>
          <ul>
            {plan.misconceptions.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h3>Scope boundaries</h3>
          <ul>
            {plan.scopeBoundaries.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h3>Research sources</h3>
          <ul>
            {plan.sources.map((source, i) => (
              <li key={i}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
