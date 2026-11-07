import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  LearnerQuiz,
  LessonQuizAttempt,
} from "../application/lesson-quizzes";
import { useApplication } from "./application-context";
import { ErrorNotice } from "./components";
import { Confetti } from "./Confetti";
import { Button } from "./primitives/Button";

export function LearnerLessonQuiz({ lessonId }: { lessonId: string }) {
  const api = useApplication().learnerQuizzes;
  const quiz = useQuery({
    queryKey: ["public-lesson-quiz", lessonId],
    queryFn: () => api!.get(lessonId),
    enabled: !!api,
  });
  const attempts = useQuery({
    queryKey: ["lesson-quiz-attempts", lessonId],
    queryFn: () => api!.attempts(lessonId),
    enabled: !!api && !!quiz.data,
  });
  if (!api) return null;
  if (quiz.error) return <ErrorNotice error={quiz.error} />;
  if (!quiz.data) return null;
  return (
    <QuizForm
      key={quiz.data.revision}
      quiz={quiz.data}
      attempts={attempts.data ?? []}
    />
  );
}

function scrollBehavior(): ScrollBehavior {
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  return reduced?.matches ? "auto" : "smooth";
}

function verdictOf(score: number, total: number, passed: boolean) {
  if (score === total)
    return {
      tone: "perfect",
      title: "Perfect score!",
      hint: "Every answer was right.",
    } as const;
  if (passed)
    return {
      tone: "passed",
      title: "Nice work, you passed",
      hint: "Review the ones marked Not quite, or try again for a perfect score.",
    } as const;
  return {
    tone: "retry",
    title: "Not there yet",
    hint: "Read the explanations on the questions marked Not quite, then try again.",
  } as const;
}

function QuizForm({
  quiz,
  attempts,
}: {
  quiz: LearnerQuiz;
  attempts: readonly LessonQuizAttempt[];
}) {
  const api = useApplication().learnerQuizzes!;
  const cache = useQueryClient();
  const panel = useRef<HTMLElement>(null);
  const summary = useRef<HTMLDivElement>(null);
  const [answers, setAnswers] = useState<readonly number[]>(() =>
    quiz.questions.map(() => -1),
  );
  const submit = useMutation({
    mutationFn: () => api.submit(quiz.lessonId, quiz.revision, answers),
    onSuccess: () =>
      cache.invalidateQueries({
        queryKey: ["lesson-quiz-attempts", quiz.lessonId],
      }),
  });
  const result = submit.data;
  const graded = new Map(
    result?.feedback.map((item) => [item.questionId, item]),
  );
  const unanswered = answers.filter((a) => a < 0).length;
  const best = attempts.length
    ? Math.max(...attempts.map((a) => a.score / a.total))
    : null;

  // Bring the score into view and tell screen readers where it is.
  useEffect(() => {
    if (!result) return;
    summary.current?.focus({ preventScroll: true });
    summary.current?.scrollIntoView?.({
      behavior: scrollBehavior(),
      block: "center",
    });
  }, [result]);

  function review(questionId: string) {
    const card = document.getElementById(`learner-question-${questionId}`);
    card?.scrollIntoView?.({ behavior: scrollBehavior(), block: "center" });
    card?.focus({ preventScroll: true });
  }
  function tryAgain() {
    submit.reset();
    setAnswers(quiz.questions.map(() => -1));
    panel.current?.scrollIntoView?.({
      behavior: scrollBehavior(),
      block: "start",
    });
  }

  const verdict =
    result && verdictOf(result.score, result.total, result.passed);
  return (
    <section
      ref={panel}
      className="quiz-panel learner-quiz"
      aria-labelledby="learner-quiz-title"
    >
      {result && verdict?.tone === "perfect" && <Confetti key={result.id} />}
      <h2 id="learner-quiz-title">Check your understanding</h2>
      <p className="muted small">
        {quiz.questions.length} questions
        {best !== null &&
          ` · ${attempts.length} recent attempts · Best score: ${Math.round(best * 100)}%`}
      </p>
      <form
        className="learner-quiz-form"
        onSubmit={(event) => {
          event.preventDefault();
          submit.mutate();
        }}
      >
        {result && verdict && (
          <div
            ref={summary}
            className="learner-summary"
            data-tone={verdict.tone}
            role="status"
            tabIndex={-1}
          >
            <p className="learner-summary-score" aria-hidden="true">
              {result.score}
              <span>/{result.total}</span>
            </p>
            <div className="learner-summary-body">
              <h3>{verdict.title}</h3>
              <p>
                You scored {result.score} of {result.total}.
              </p>
              <p className="muted">{verdict.hint}</p>
              <ol
                className="learner-summary-marks"
                aria-label="Results by question"
              >
                {quiz.questions.map((question, index) => {
                  const right = graded.get(question.id)?.correct;
                  return (
                    <li key={question.id}>
                      <button
                        type="button"
                        data-correct={right ? "true" : "false"}
                        aria-label={`Question ${index + 1}: ${right ? "correct" : "not quite"}`}
                        onClick={() => review(question.id)}
                      >
                        {index + 1}
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>
            <Button type="button" variant="secondary" onClick={tryAgain}>
              Try again
            </Button>
          </div>
        )}
        {quiz.questions.map((question, index) => {
          const feedback = graded.get(question.id);
          return (
            <fieldset
              key={question.id}
              id={`learner-question-${question.id}`}
              className="learner-question"
              data-result={
                feedback ? (feedback.correct ? "correct" : "wrong") : undefined
              }
              tabIndex={-1}
              disabled={submit.isPending || !!result}
            >
              <legend>
                <span className="learner-number" aria-hidden="true">
                  {feedback ? (feedback.correct ? "✓" : "✕") : index + 1}
                </span>
                <span>
                  <span className="sr-only">Question {index + 1}. </span>
                  {question.prompt}
                </span>
              </legend>
              <div className="quiz-options">
                {question.options.map((option, optionIndex) => {
                  const picked = answers[index] === optionIndex;
                  return (
                    <label
                      className={picked ? "chosen" : undefined}
                      data-picked={
                        result && picked
                          ? feedback?.correct
                            ? "right"
                            : "wrong"
                          : undefined
                      }
                      key={optionIndex}
                    >
                      <input
                        type="radio"
                        name={question.id}
                        value={optionIndex}
                        checked={picked}
                        onChange={() =>
                          setAnswers((current) =>
                            current.map((value, i) =>
                              i === index ? optionIndex : value,
                            ),
                          )
                        }
                      />
                      <span className="answer-letter" aria-hidden="true">
                        {String.fromCharCode(65 + optionIndex)}
                      </span>
                      <span className="learner-option-text">{option}</span>
                      {result && picked && (
                        <span
                          className="learner-option-mark"
                          aria-hidden="true"
                        >
                          {feedback?.correct
                            ? "✓ Your answer"
                            : "✕ Your answer"}
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
              {feedback && (
                <div className="learner-feedback">
                  <p className="learner-verdict">
                    {feedback.correct ? "Correct" : "Not quite"}
                  </p>
                  {feedback.explanation && <p>{feedback.explanation}</p>}
                </div>
              )}
            </fieldset>
          );
        })}
        {submit.error && <ErrorNotice error={submit.error} />}
        {!result && (
          <div className="learner-submit">
            <Button type="submit" disabled={unanswered > 0 || submit.isPending}>
              {submit.isPending ? "Grading…" : "Submit answers"}
            </Button>
            <p className="muted small" aria-live="polite">
              {unanswered > 0
                ? `${unanswered} ${unanswered === 1 ? "question" : "questions"} left to answer`
                : "All answered. Ready when you are."}
            </p>
          </div>
        )}
      </form>
    </section>
  );
}
