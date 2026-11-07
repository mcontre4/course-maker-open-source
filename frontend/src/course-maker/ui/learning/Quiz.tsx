import { hasLessonArtifacts } from "./lesson-view";
import { useState } from "react";
import { Button } from "../primitives/Button";
import type {
  CourseResponse,
  LessonResponse,
  QuizResultResponse,
} from "../../application/dto";
import { useApplication, useCourseMutation } from "../application-context";
import { ErrorNotice, LinkButton, Progress } from "../components";

export function Quiz({
  course,
  lesson,
  onBack,
}: {
  course: CourseResponse;
  lesson: LessonResponse;
  onBack: () => void;
}) {
  const app = useApplication();
  const submit = useCourseMutation(app.submitQuiz.execute.bind(app.submitQuiz));
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<number[]>([]);
  const [result, setResult] = useState<QuizResultResponse | null>(null);
  const next = course.chapters
    .flatMap((c) => c.lessons)
    .find((l) => l.id !== lesson.id && !course.completed.includes(l.id));
  if (!hasLessonArtifacts(lesson) || !course.reviewed.includes(lesson.id))
    return (
      <section className="panel">
        <h1>Watch the video first.</h1>
        <p>Finish the lesson video before trying its quiz.</p>
        <Button onClick={onBack}>Back to lesson</Button>
      </section>
    );
  if (!lesson.quiz.length)
    return (
      <section className="panel">
        <h1>Your quiz isn’t ready yet.</h1>
        <p>Come back when the questions for this lesson are available.</p>
        <Button onClick={onBack}>Back to lesson</Button>
      </section>
    );
  if (result)
    return (
      <section className="quiz-result sage">
        <span className="result-symbol" aria-hidden="true">
          {result.passed ? "✓" : "↻"}
        </span>
        <h1>
          {result.passed
            ? "One more lesson. One step further."
            : "A little more practice."}
        </h1>
        <p>{lesson.title}</p>
        <strong className="score">
          {result.score} / {result.total}
        </strong>
        <p>
          {result.passed
            ? "Lesson complete. Your progress has been saved."
            : "Review the explanations and try again. Answer every question correctly to complete this lesson."}
        </p>
        <ol className="quiz-feedback">
          {result.feedback.map((f, i) => (
            <li key={i}>
              <strong>
                {f.correct ? "✓" : "↻"} Question {i + 1}
              </strong>
              <p>{f.explanation}</p>
            </li>
          ))}
        </ol>
        {result.passed ? (
          <>
            <Progress
              completed={course.completed.length}
              total={course.chapters.flatMap((c) => c.lessons).length}
            />
            <p className="progress-label">
              {course.completed.length} lessons completed
            </p>
            {next ? (
              <LinkButton to={"/courses/" + course.id + "/lessons/" + next.id}>
                Next lesson: {next.title} →
              </LinkButton>
            ) : (
              <LinkButton to="/">Back to my learning →</LinkButton>
            )}
          </>
        ) : (
          <Button
            onClick={() => {
              setResult(null);
              setStep(0);
              setAnswers([]);
            }}
          >
            Try the quiz again
          </Button>
        )}
        <Button variant="secondary" onClick={onBack}>
          Review this lesson
        </Button>
      </section>
    );
  const question = lesson.quiz[step];
  return (
    <form
      className="panel quiz-panel"
      onSubmit={async (e) => {
        e.preventDefault();
        if (answers[step] === undefined || submit.isPending) return;
        if (step < lesson.quiz.length - 1) {
          setStep((n) => n + 1);
          return;
        }
        try {
          setResult(
            await submit.mutateAsync({
              courseId: course.id,
              lessonId: lesson.id,
              answers,
            }),
          );
        } catch {
          /* Visible error below. */
        }
      }}
    >
      <span className="pill lavender">A QUICK CHECK-IN</span>
      <h1>Let’s see what stuck.</h1>
      <p className="muted">
        {lesson.title}
        <br />
        {lesson.quiz.length} questions · No timer · You can try again
      </p>
      <Progress
        completed={step + 1}
        total={lesson.quiz.length}
        label="Quiz question progress"
      />
      <fieldset key={question.id}>
        <legend>
          <span className="eyebrow">
            QUESTION {step + 1} OF {lesson.quiz.length}
          </span>
          <span className="question-title">{question.prompt}</span>
        </legend>
        <div className="quiz-options">
          {question.options.map((option, index) => (
            <label
              className={answers[step] === index ? "chosen" : ""}
              key={index}
            >
              <input
                type="radio"
                name={question.id}
                value={index}
                checked={answers[step] === index}
                onChange={() =>
                  setAnswers((current) => {
                    const next = [...current];
                    next[step] = index;
                    return next;
                  })
                }
              />
              <span className="answer-letter" aria-hidden="true">
                {String.fromCharCode(65 + index)}
              </span>
              <span>{option}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <ErrorNotice error={submit.error} />
      <div className="quiz-actions">
        {step > 0 ? (
          <Button
            variant="secondary"
            disabled={submit.isPending}
            onClick={() => setStep((n) => n - 1)}
          >
            Previous question
          </Button>
        ) : null}
        <Button
          type="submit"
          disabled={answers[step] === undefined || submit.isPending}
        >
          {submit.isPending
            ? "Checking…"
            : step === lesson.quiz.length - 1
              ? "Check my answers"
              : "Next question →"}
        </Button>
      </div>
      <p className="muted small">
        Sample questions for this demo. Your answers help you practice.
      </p>
    </form>
  );
}
