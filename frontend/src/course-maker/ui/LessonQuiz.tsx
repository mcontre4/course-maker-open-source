import { useState } from "react";
import {
  blankQuestion,
  questionProblem,
  quizLimits,
  quizProblem,
  tidyQuestions,
  type QuizQuestion,
} from "../application/lesson-quizzes";
import type { StandaloneLessonResponse } from "../application/standalone-lessons";
import { useApplication } from "./application-context";
import { ErrorNotice } from "./components";
import {
  useGenerateQuiz,
  useLessonQuiz,
  useQuizMutation,
} from "./lesson-quiz-context";
import { Button } from "./primitives/Button";

const letter = (index: number) => String.fromCharCode(65 + index);
const count = (n: number) => `${n} question${n === 1 ? "" : "s"}`;

function QuestionResult({
  question,
  index,
}: {
  question: QuizQuestion;
  index: number;
}) {
  return (
    <>
      <p className="quiz-prompt">
        <span className="quiz-number" aria-hidden="true">
          {index + 1}
        </span>
        {question.prompt}
      </p>
      <ol className="quiz-answers" type="A">
        {question.options.map((option, at) => (
          <li
            key={at}
            data-correct={at === question.correctIndex}
            aria-label={
              at === question.correctIndex
                ? `${option} (correct answer)`
                : undefined
            }
          >
            <span className="quiz-letter" aria-hidden="true">
              {at === question.correctIndex ? "✓" : letter(at)}
            </span>
            <span>{option}</span>
          </li>
        ))}
      </ol>
      {question.explanation && (
        <p className="quiz-explanation">
          <b>Why: </b>
          {question.explanation}
        </p>
      )}
    </>
  );
}

/** Read-only quiz shown beneath the finished video. */
export function LessonQuizPreview({
  lesson,
  onEdit,
}: {
  lesson: StandaloneLessonResponse;
  onEdit(): void;
}) {
  const quiz = useLessonQuiz(lesson.id);
  const generate = useGenerateQuiz(lesson);
  const questions = quiz.data?.questions ?? [];
  const waiting = quiz.isPending || generate.isPending;
  return (
    <section className="quiz-preview" aria-labelledby="quiz-preview-title">
      <div className="quiz-preview-head">
        <div>
          <span className="quiz-eyebrow">QUIZ</span>
          <h2 id="quiz-preview-title">Check your understanding</h2>
          <p className="muted small">
            {questions.length
              ? `${count(questions.length)} · multiple choice · learners answer these after watching`
              : "A short multiple-choice check on this lesson."}
          </p>
        </div>
        <Button variant="secondary" onClick={onEdit}>
          {questions.length ? "Edit quiz" : "Set up quiz"}
        </Button>
      </div>
      {questions.length ? (
        <div className="quiz-preview-list">
          {questions.map((question, index) => (
            <details key={question.id}>
              <summary>
                <span className="quiz-number" aria-hidden="true">
                  {index + 1}
                </span>
                <span>{question.prompt}</span>
              </summary>
              <div className="quiz-preview-body">
                <ol className="quiz-answers" type="A">
                  {question.options.map((option, at) => (
                    <li key={at} data-correct={at === question.correctIndex}>
                      <span className="quiz-letter" aria-hidden="true">
                        {at === question.correctIndex ? "✓" : letter(at)}
                      </span>
                      <span>{option}</span>
                    </li>
                  ))}
                </ol>
                {question.explanation && (
                  <p className="quiz-explanation">{question.explanation}</p>
                )}
              </div>
            </details>
          ))}
        </div>
      ) : waiting ? (
        <p className="quiz-empty" role="status">
          <span className="loading-spinner" aria-hidden="true" />
          Drafting questions from your lesson…
        </p>
      ) : (
        <p className="quiz-empty">
          No quiz yet. Draft one from your outline, then adjust it however you
          like.
          <Button
            variant="secondary"
            onClick={() => generate.mutate()}
            disabled={!lesson.content.plan}
          >
            Generate quiz
          </Button>
        </p>
      )}
      <ErrorNotice error={generate.error} />
    </section>
  );
}

/** Quiz tab of the lesson studio: review, edit, add, remove and regenerate. */
export function LessonQuizPanel({
  lesson,
  disabled = false,
  onDirtyChange,
}: {
  lesson: StandaloneLessonResponse;
  disabled?: boolean;
  onDirtyChange(dirty: boolean): void;
}) {
  const app = useApplication().quizzes;
  const quiz = useLessonQuiz(lesson.id);
  const generate = useGenerateQuiz(lesson);
  const [draftRevision, setDraftRevision] = useState(0);
  const save = useQuizMutation(async (questions: readonly QuizQuestion[]) => {
    if (!app) throw new Error("Quizzes are unavailable.");
    return app.save.execute({
      lessonId: lesson.id,
      questions,
      expectedRevision: draftRevision,
    });
  });
  const [draft, setDraft] = useState<readonly QuizQuestion[] | null>(null);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const saved = quiz.data?.questions;
  const generating = generate.isPending;

  const edit = (next: readonly QuizQuestion[] | null) => {
    if (next !== null && draft === null)
      setDraftRevision(quiz.data?.revision ?? 0);
    setDraft(next);
    onDirtyChange(next !== null);
  };
  const change = (index: number, patch: Partial<QuizQuestion>) =>
    setDraft((current) =>
      current
        ? current.map((q, at) => (at === index ? { ...q, ...patch } : q))
        : current,
    );

  if (quiz.isPending && app)
    return (
      <section className="lesson-quiz" aria-label="Lesson quiz">
        <p className="quiz-empty" role="status">
          <span className="loading-spinner" aria-hidden="true" />
          Loading your quiz…
        </p>
      </section>
    );

  if (!saved) {
    return (
      <section className="lesson-quiz quiz-blank" aria-label="Lesson quiz">
        <h2>
          {generating ? "Drafting your quiz…" : "Add a quiz to this lesson"}
        </h2>
        <p className="muted">
          {generating
            ? "Questions are being drafted from your outline."
            : lesson.content.plan
              ? "We’ll draft multiple-choice questions from your outline. You can edit, add or remove any of them."
              : "Create the lesson outline first — questions are drafted from it."}
        </p>
        {generating ? (
          <span className="loading-spinner" aria-hidden="true" />
        ) : (
          <div className="workflow-inline-actions">
            <Button
              disabled={disabled || !lesson.content.plan}
              onClick={() => generate.mutate()}
            >
              Generate quiz from outline
            </Button>
            <Button
              variant="secondary"
              disabled={disabled}
              onClick={() => edit([blankQuestion([])])}
            >
              Write my own
            </Button>
          </div>
        )}
        <ErrorNotice error={generate.error} />
        {draft && (
          <QuizEditor
            draft={draft}
            pending={save.isPending}
            error={save.error}
            change={change}
            setDraft={setDraft}
            onSave={() => save.mutate(draft, { onSuccess: () => edit(null) })}
            onCancel={() => {
              edit(null);
              save.reset();
            }}
          />
        )}
      </section>
    );
  }

  return (
    <section className="lesson-quiz" aria-label="Lesson quiz">
      <div className="workflow-section-heading">
        <div>
          <h2>Quiz</h2>
          <p className="muted small">
            {count(saved.length)} · multiple choice ·{" "}
            {quiz.data?.origin === "edited"
              ? "edited by you"
              : "drafted from your outline"}
          </p>
        </div>
        {!draft && (
          <div className="workflow-inline-actions">
            {confirmReplace ? (
              <>
                <span className="quiz-confirm">Replace your questions?</span>
                <Button
                  variant="secondary"
                  disabled={disabled || generating}
                  onClick={() =>
                    generate.mutate(undefined, {
                      onSettled: () => setConfirmReplace(false),
                    })
                  }
                >
                  {generating ? "Regenerating…" : "Yes, regenerate"}
                </Button>
                <Button
                  variant="secondary"
                  disabled={generating}
                  onClick={() => setConfirmReplace(false)}
                >
                  Keep mine
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="secondary"
                  disabled={disabled || !lesson.content.plan}
                  onClick={() => setConfirmReplace(true)}
                >
                  Regenerate quiz
                </Button>
                <Button
                  variant="secondary"
                  disabled={disabled}
                  onClick={() => edit(saved)}
                >
                  Edit quiz
                </Button>
              </>
            )}
          </div>
        )}
      </div>
      {draft ? (
        <QuizEditor
          draft={draft}
          pending={save.isPending}
          error={save.error}
          change={change}
          setDraft={setDraft}
          onSave={() => save.mutate(draft, { onSuccess: () => edit(null) })}
          onCancel={() => {
            edit(null);
            save.reset();
          }}
        />
      ) : (
        <div className="quiz-list">
          {saved.map((question, index) => (
            <article className="quiz-card" key={question.id}>
              <QuestionResult question={question} index={index} />
            </article>
          ))}
        </div>
      )}
      <ErrorNotice error={generate.error} />
    </section>
  );
}

function QuizEditor({
  draft,
  pending,
  error,
  change,
  setDraft,
  onSave,
  onCancel,
}: {
  draft: readonly QuizQuestion[];
  pending: boolean;
  error: unknown;
  change(index: number, patch: Partial<QuizQuestion>): void;
  setDraft(
    update: (
      current: readonly QuizQuestion[] | null,
    ) => readonly QuizQuestion[] | null,
  ): void;
  onSave(): void;
  onCancel(): void;
}) {
  const [touched, setTouched] = useState(false);
  const problem = quizProblem(tidyQuestions(draft));
  const move = (index: number, by: -1 | 1) =>
    setDraft((current) => {
      if (!current) return current;
      const next = [...current];
      [next[index], next[index + by]] = [next[index + by], next[index]];
      return next;
    });
  return (
    <form
      className="quiz-editor"
      onSubmit={(event) => {
        event.preventDefault();
        setTouched(true);
        if (!problem && !pending) onSave();
      }}
    >
      {draft.map((question, index) => {
        const own = touched ? questionProblem(tidyQuestionOne(question)) : null;
        return (
          <fieldset
            className="quiz-card quiz-edit-card"
            key={question.id}
            disabled={pending}
          >
            <legend className="sr-only">Question {index + 1}</legend>
            <div className="quiz-card-bar">
              <span className="quiz-number" aria-hidden="true">
                {index + 1}
              </span>
              <span className="quiz-card-title">Question {index + 1}</span>
              <div className="quiz-card-tools">
                <button
                  type="button"
                  aria-label={`Move question ${index + 1} up`}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move question ${index + 1} down`}
                  disabled={index === draft.length - 1}
                  onClick={() => move(index, 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="danger"
                  aria-label={`Delete question ${index + 1}`}
                  disabled={draft.length === 1}
                  onClick={() =>
                    setDraft((current) =>
                      current
                        ? current.filter((_, at) => at !== index)
                        : current,
                    )
                  }
                >
                  Delete
                </button>
              </div>
            </div>
            <label className="quiz-field">
              <span>Question</span>
              <textarea
                aria-label={`Question ${index + 1} text`}
                rows={2}
                maxLength={quizLimits.prompt}
                value={question.prompt}
                placeholder="What should learners be able to answer?"
                onChange={(e) => change(index, { prompt: e.target.value })}
              />
            </label>
            <div
              className="quiz-field"
              role="group"
              aria-label={`Answers for question ${index + 1}`}
            >
              <span>Answers · select the correct one</span>
              {question.options.map((option, at) => (
                <div
                  className="quiz-option-row"
                  data-correct={at === question.correctIndex}
                  key={at}
                >
                  <input
                    type="radio"
                    name={`${question.id}-correct`}
                    aria-label={`Mark answer ${letter(at)} of question ${index + 1} as correct`}
                    checked={at === question.correctIndex}
                    onChange={() => change(index, { correctIndex: at })}
                  />
                  <span className="quiz-letter" aria-hidden="true">
                    {letter(at)}
                  </span>
                  <input
                    type="text"
                    aria-label={`Answer ${letter(at)} of question ${index + 1}`}
                    maxLength={quizLimits.option}
                    value={option}
                    placeholder={`Answer ${letter(at)}`}
                    onChange={(e) =>
                      change(index, {
                        options: question.options.map((o, i) =>
                          i === at ? e.target.value : o,
                        ),
                      })
                    }
                  />
                  <button
                    type="button"
                    className="quiz-remove"
                    aria-label={`Remove answer ${letter(at)} of question ${index + 1}`}
                    disabled={question.options.length <= quizLimits.minOptions}
                    onClick={() =>
                      change(index, {
                        options: question.options.filter((_, i) => i !== at),
                        correctIndex:
                          question.correctIndex === at
                            ? 0
                            : question.correctIndex > at
                              ? question.correctIndex - 1
                              : question.correctIndex,
                      })
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
              {question.options.length < quizLimits.maxOptions && (
                <button
                  type="button"
                  className="quiz-add-answer"
                  onClick={() =>
                    change(index, { options: [...question.options, ""] })
                  }
                >
                  + Add answer
                </button>
              )}
            </div>
            <label className="quiz-field">
              <span>Explanation · shown after answering (optional)</span>
              <textarea
                aria-label={`Explanation for question ${index + 1}`}
                rows={2}
                maxLength={quizLimits.explanation}
                value={question.explanation}
                onChange={(e) => change(index, { explanation: e.target.value })}
              />
            </label>
            {own && (
              <p className="quiz-problem" role="alert">
                {own}
              </p>
            )}
          </fieldset>
        );
      })}
      <button
        type="button"
        className="quiz-add-question"
        disabled={pending || draft.length >= quizLimits.questions}
        onClick={() =>
          setDraft((current) =>
            current ? [...current, blankQuestion(current)] : current,
          )
        }
      >
        + Add question
      </button>
      <div className="quiz-savebar">
        <p
          className="muted small"
          role={touched && problem ? "alert" : undefined}
        >
          {touched && problem
            ? problem
            : `${count(draft.length)} · multiple choice`}
        </p>
        <div className="workflow-inline-actions">
          <Button type="submit" disabled={pending}>
            {pending ? "Saving…" : "Save quiz"}
          </Button>
          <Button variant="secondary" disabled={pending} onClick={onCancel}>
            Cancel quiz edits
          </Button>
        </div>
      </div>
      <ErrorNotice error={error} />
    </form>
  );
}

function tidyQuestionOne(question: QuizQuestion) {
  return tidyQuestions([question])[0];
}
