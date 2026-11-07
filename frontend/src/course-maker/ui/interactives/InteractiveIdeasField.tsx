import {
  briefProblem,
  interactiveLimits,
} from "../../application/lesson-interactives";

/** Lets someone describe interactives before the lesson they belong to exists. */
export function InteractiveIdeasField({
  ideas,
  onChange,
  text,
  onTextChange,
  disabled,
}: {
  ideas: readonly string[];
  onChange(ideas: readonly string[]): void;
  /** Held by the form, so text not yet added still counts when it is submitted. */
  text: string;
  onTextChange(text: string): void;
  disabled: boolean;
}) {
  const full = ideas.length >= interactiveLimits.perLesson;
  const add = () => {
    if (briefProblem(text)) return;
    onChange([...ideas, text.trim()]);
    onTextChange("");
  };
  return (
    <div className="interactive-ideas-field">
      <p className="muted small">
        Optional. Describe something learners can play with to make the lesson
        stick. We’ll build it alongside your lesson, and you can add more at any
        time.
      </p>
      {!!ideas.length && (
        <ul>
          {ideas.map((idea) => (
            <li key={idea}>
              <span>{idea}</span>
              <button
                type="button"
                className="quiz-remove"
                aria-label={`Remove: ${idea}`}
                disabled={disabled}
                onClick={() =>
                  onChange(ideas.filter((other) => other !== idea))
                }
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <label htmlFor="lesson-interactive-idea">Describe an interactive</label>
      <textarea
        id="lesson-interactive-idea"
        rows={2}
        maxLength={interactiveLimits.brief}
        placeholder="e.g. A pendulum where learners change gravity, length and weight"
        value={text}
        disabled={disabled}
        onChange={(event) => onTextChange(event.target.value)}
      />
      <button
        type="button"
        className="quiz-add-answer"
        disabled={
          disabled ||
          full ||
          !!briefProblem(text) ||
          ideas.includes(text.trim())
        }
        onClick={add}
      >
        + Add this interactive
      </button>
    </div>
  );
}
