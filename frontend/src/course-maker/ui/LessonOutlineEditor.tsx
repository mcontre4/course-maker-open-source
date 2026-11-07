import { useRef, useState, type ReactNode } from "react";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  closestCenter,
  pointerWithin,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  sortableKeyboardCoordinates,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { LessonPlanResponse } from "../application/dto";
import type { SaveOutlineRequest } from "../application/standalone-lessons";
import { Button } from "./primitives/Button";
import { ErrorNotice } from "./components";

type Outline = SaveOutlineRequest["outline"];
const lines = (values: readonly string[]) =>
  values
    .flatMap((value) => value.split("\n"))
    .filter((value) => value.trim().length > 0);

function InlineText({
  label,
  value,
  onChange,
  required = true,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <span className="outline-inline-text" data-value={value || " "}>
      <textarea
        aria-label={label}
        placeholder={label}
        rows={1}
        required={required}
        maxLength={6000}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </span>
  );
}

function ListField({
  label,
  values,
  onChange,
  ordered = false,
}: {
  label: string;
  values: readonly string[];
  onChange: (values: string[]) => void;
  ordered?: boolean;
}) {
  const List = ordered ? "ol" : "ul";
  return (
    <>
      <List>
        {values.map((value, index) => (
          <li key={index} className="outline-edit-item">
            <InlineText
              label={index === 0 ? label : `${label} ${index + 1}`}
              value={value}
              required={false}
              onChange={(text) =>
                onChange(values.map((item, i) => (i === index ? text : item)))
              }
            />
            <button
              type="button"
              className="outline-quiet-action outline-remove"
              aria-label={`Remove ${label} ${index + 1}`}
              onClick={() => onChange(values.filter((_, i) => i !== index))}
            >
              ×
            </button>
          </li>
        ))}
      </List>
      <button
        type="button"
        className="outline-quiet-action"
        onClick={() => onChange([...values, ""])}
      >
        + Add {label.toLowerCase()}
      </button>
    </>
  );
}

function SortableChapter({
  id,
  index,
  disabled,
  onMove,
  children,
}: {
  id: number;
  index: number;
  disabled: boolean;
  onMove: (to: number) => void;
  children: ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id,
    disabled,
    transition: { duration: 220, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
  });
  return (
    <li
      ref={setNodeRef}
      data-outline-chapter={index}
      className={isDragging ? "is-dragging" : undefined}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <button
        ref={setActivatorNodeRef}
        type="button"
        className="beat-number outline-drag-handle"
        {...attributes}
        {...listeners}
        disabled={disabled}
        aria-label={`Reorder chapter ${index + 1}`}
        aria-describedby="chapter-drag-help"
        onKeyDown={(event) => {
          if (
            !isDragging &&
            (event.key === "ArrowUp" || event.key === "ArrowDown")
          ) {
            event.preventDefault();
            onMove(index + (event.key === "ArrowUp" ? -1 : 1));
          } else {
            listeners?.onKeyDown?.(event);
          }
        }}
      >
        <span>{String(index + 1).padStart(2, "0")}</span>
        <span className="drag-grip" aria-hidden="true">
          ⠿
        </span>
      </button>
      {children}
    </li>
  );
}

export function LessonOutlineEditor({
  plan,
  minutes,
  topics,
  pending,
  error,
  onSave,
  onCancel,
}: {
  plan: LessonPlanResponse;
  minutes: number;
  topics: readonly string[];
  pending: boolean;
  error: Error | null;
  onSave: (outline: Outline) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Outline>(() => {
    const { lessonId: _lessonId, sources: _sources, ...outline } = plan;
    return outline;
  });
  const [validation, setValidation] = useState("");
  const nextKey = useRef(plan.beats.length);
  const [beatKeys, setBeatKeys] = useState(() =>
    plan.beats.map((_, index) => index),
  );
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const [announcement, setAnnouncement] = useState("");
  const moveBeat = (from: number, to: number) => {
    if (from === to || to < 0 || to >= draft.beats.length || pending) return;
    const beats = [...draft.beats];
    beats.splice(to, 0, beats.splice(from, 1)[0]);
    const keys = [...beatKeys];
    keys.splice(to, 0, keys.splice(from, 1)[0]);
    setBeatKeys(keys);
    setDraft({ ...draft, beats });
    setAnnouncement(`Chapter moved to position ${to + 1} of ${beats.length}.`);
  };
  const total = draft.beats.reduce((sum, beat) => sum + beat.seconds, 0);
  const listFields = [
    ["objectives", "Learning objectives"],
    ["assumedKnowledge", "Assumed knowledge"],
    ["introducedKnowledge", "Introduced knowledge"],
    ["requiredFacts", "Required facts"],
    ["equations", "Equations"],
    ["misconceptions", "Misconceptions"],
    ["scopeBoundaries", "Scope boundaries"],
  ] as const;
  const updateBeat = (
    index: number,
    change: Partial<Outline["beats"][number]>,
  ) =>
    setDraft({
      ...draft,
      beats: draft.beats.map((beat, i) =>
        i === index ? { ...beat, ...change } : beat,
      ),
    });
  return (
    <form
      className="outline-editor"
      aria-label="Edit lesson outline"
      onSubmit={(event) => {
        event.preventDefault();
        const outline: Outline = {
          ...draft,
          recommendedVideoMinutes:
            draft.feasibilityStatus === "infeasible" &&
            draft.recommendedVideoMinutes != null
              ? Math.ceil(total / 60)
              : draft.recommendedVideoMinutes,
          objectives: lines(draft.objectives),
          assumedKnowledge: lines(draft.assumedKnowledge),
          introducedKnowledge: lines(draft.introducedKnowledge),
          requiredFacts: lines(draft.requiredFacts),
          equations: lines(draft.equations),
          misconceptions: lines(draft.misconceptions),
          scopeBoundaries: lines(draft.scopeBoundaries),
          beats: draft.beats.map((beat) => ({
            ...beat,
            concepts: lines(beat.concepts),
          })),
          examples: draft.examples.map((example) => ({
            ...example,
            steps: lines(example.steps),
          })),
        };
        const authoredText = [
          ...outline.objectives,
          ...outline.assumedKnowledge,
          ...outline.introducedKnowledge,
          ...outline.requiredFacts,
          ...outline.equations,
          ...outline.misconceptions,
          ...outline.scopeBoundaries,
          ...outline.beats.flatMap((beat) => [
            beat.title,
            beat.purpose,
            beat.teachingNotes,
            ...beat.concepts,
          ]),
          ...outline.examples.flatMap((example) => [
            example.problem,
            ...example.steps,
            example.result,
          ]),
        ];
        let issue = "";
        if (
          [
            outline.objectives,
            outline.introducedKnowledge,
            outline.requiredFacts,
            outline.scopeBoundaries,
          ].some((items) => !items.length)
        )
          issue =
            "Add learning objectives, introduced knowledge, required facts and scope boundaries.";
        else if (outline.objectives.some((objective) => objective.length > 200))
          issue = "Keep each learning objective within 200 characters.";
        else if (authoredText.some((value) => !value.trim()))
          issue = "Fill in every teaching beat and worked example field.";
        else if (authoredText.some((value) => value.length > 6000))
          issue = "Keep each outline item within 6000 characters.";
        else if (!outline.beats.length || !outline.examples.length)
          issue = "Keep at least one teaching beat and one worked example.";
        else if (outline.beats.some((beat) => !beat.concepts.length))
          issue = "Each teaching beat needs concepts.";
        else if (
          outline.beats.some(
            (beat) =>
              Boolean(beat.checkQuestion.trim()) !==
              Boolean(beat.expectedAnswer.trim()),
          )
        )
          issue =
            "A diagnostic check needs both a question and an expected answer.";
        else if (
          outline.feasibilityStatus === "infeasible" &&
          (outline.recommendedVideoMinutes == null ||
            total <= minutes * 60 ||
            (outline.recommendedVideoMinutes != null &&
              total > outline.recommendedVideoMinutes * 60))
        )
          issue =
            "An infeasible lesson needs a duration recommendation that accommodates its teaching estimates.";
        else if (
          outline.feasibilityStatus === "feasible" &&
          total !== minutes * 60
        )
          issue = `Teaching beat timing must total exactly ${minutes * 60} seconds.`;
        else if (
          outline.feasibilityStatus == null &&
          (total > 600 || Math.abs(total - minutes * 60) > 30)
        )
          issue = `Teaching beat timing must total within 30 seconds of ${minutes * 60} seconds and stay within 600 seconds.`;
        else if (
          !topics.every((topic) =>
            outline.beats.some((beat) => beat.concepts.includes(topic)),
          )
        )
          issue = `Keep the lesson topics covered in teaching beat concepts: ${topics.join(", ")}.`;
        setValidation(issue);
        if (!issue) onSave(outline);
      }}
    >
      <fieldset disabled={pending}>
        <legend className="sr-only">Outline content</legend>
        <div className="outline-objectives">
          <p className="eyebrow">WHAT YOU’LL LEARN</p>
          <ListField
            label="Learning objectives"
            values={draft.objectives}
            onChange={(objectives) => setDraft({ ...draft, objectives })}
          />
        </div>
        <p className="sr-only" id="chapter-drag-help">
          Drag to reorder chapters, or use the Up and Down arrow keys. Press
          Escape to cancel dragging. You can also press Space to pick up or drop
          a chapter.
        </p>
        <p className="sr-only" role="status">
          {announcement}
        </p>
        <DndContext
          sensors={sensors}
          collisionDetection={(args) =>
            args.pointerCoordinates && pointerWithin(args).length === 0
              ? []
              : closestCenter(args)
          }
          onDragEnd={({ active, over }) => {
            if (over && active.id !== over.id)
              moveBeat(
                beatKeys.indexOf(Number(active.id)),
                beatKeys.indexOf(Number(over.id)),
              );
          }}
        >
          <SortableContext
            items={beatKeys}
            strategy={verticalListSortingStrategy}
          >
            <ol className="teaching-timeline">
              {draft.beats.map((beat, index) => (
                <SortableChapter
                  key={beatKeys[index]}
                  id={beatKeys[index]}
                  index={index}
                  disabled={pending}
                  onMove={(to) => moveBeat(index, to)}
                >
                  <div>
                    <div className="beat-heading">
                      <h3>
                        <InlineText
                          label={`Beat ${index + 1}: Title`}
                          value={beat.title}
                          onChange={(title) => updateBeat(index, { title })}
                        />
                      </h3>
                      <span>
                        <input
                          className="outline-seconds"
                          aria-label={`Beat ${index + 1}: Seconds`}
                          type="number"
                          min={1}
                          max={
                            draft.feasibilityStatus === "infeasible"
                              ? undefined
                              : 600
                          }
                          step={1}
                          required
                          value={beat.seconds || ""}
                          onChange={(event) =>
                            updateBeat(index, {
                              seconds: Number(event.target.value),
                            })
                          }
                        />
                        s
                      </span>
                    </div>
                    <p>
                      <InlineText
                        label={`Beat ${index + 1}: Purpose`}
                        value={beat.purpose}
                        onChange={(purpose) => updateBeat(index, { purpose })}
                      />
                    </p>
                    <p className="muted teaching-notes">
                      <InlineText
                        label={`Beat ${index + 1}: Teaching notes`}
                        value={beat.teachingNotes}
                        onChange={(teachingNotes) =>
                          updateBeat(index, { teachingNotes })
                        }
                      />
                    </p>
                    <details>
                      <summary>Check your understanding</summary>
                      <p>
                        <InlineText
                          required={false}
                          label={`Beat ${index + 1}: Check question`}
                          value={beat.checkQuestion}
                          onChange={(checkQuestion) =>
                            updateBeat(index, { checkQuestion })
                          }
                        />
                      </p>
                      <p className="muted">
                        <InlineText
                          required={false}
                          label={`Beat ${index + 1}: Expected answer`}
                          value={beat.expectedAnswer}
                          onChange={(expectedAnswer) =>
                            updateBeat(index, { expectedAnswer })
                          }
                        />
                      </p>
                      <p className="eyebrow">Concepts</p>
                      <ListField
                        label={`Beat ${index + 1}: Concepts`}
                        values={beat.concepts}
                        onChange={(concepts) => updateBeat(index, { concepts })}
                      />
                    </details>
                    <button
                      type="button"
                      className="outline-quiet-action"
                      disabled={draft.beats.length === 1}
                      aria-label={`Remove beat ${index + 1}`}
                      onClick={() => {
                        setBeatKeys(beatKeys.filter((_, i) => i !== index));
                        setDraft({
                          ...draft,
                          beats: draft.beats.filter((_, i) => i !== index),
                        });
                      }}
                    >
                      Remove chapter
                    </button>
                  </div>
                </SortableChapter>
              ))}
            </ol>
          </SortableContext>
        </DndContext>
        <button
          type="button"
          className="outline-quiet-action"
          aria-label="Add teaching beat"
          disabled={draft.beats.length >= 30}
          onClick={() => {
            setBeatKeys([...beatKeys, nextKey.current++]);
            setDraft({
              ...draft,
              beats: [
                ...draft.beats,
                {
                  title: "",
                  purpose: "",
                  teachingNotes: "",
                  concepts: [...topics],
                  seconds: 30,
                  checkQuestion: "",
                  expectedAnswer: "",
                },
              ],
            });
          }}
        >
          + Add chapter
        </button>
        <section className="lesson-examples">
          <p className="eyebrow">BRING IT TO LIFE</p>
          {draft.examples.map((example, index) => {
            const updateExample = (
              change: Partial<Outline["examples"][number]>,
            ) =>
              setDraft({
                ...draft,
                examples: draft.examples.map((item, i) =>
                  i === index ? { ...item, ...change } : item,
                ),
              });
            return (
              <article key={index}>
                <h3>
                  <InlineText
                    label={`Example ${index + 1}: Problem`}
                    value={example.problem}
                    onChange={(problem) => updateExample({ problem })}
                  />
                </h3>
                <ListField
                  ordered
                  label={`Example ${index + 1}: Steps`}
                  values={example.steps}
                  onChange={(steps) => updateExample({ steps })}
                />
                <p>
                  <InlineText
                    label={`Example ${index + 1}: Result`}
                    value={example.result}
                    onChange={(result) => updateExample({ result })}
                  />
                </p>
                <button
                  type="button"
                  className="outline-quiet-action"
                  disabled={draft.examples.length === 1}
                  aria-label={`Remove example ${index + 1}`}
                  onClick={() =>
                    setDraft({
                      ...draft,
                      examples: draft.examples.filter((_, i) => i !== index),
                    })
                  }
                >
                  Remove example
                </button>
              </article>
            );
          })}
          <button
            type="button"
            className="outline-quiet-action"
            onClick={() =>
              setDraft({
                ...draft,
                examples: [
                  ...draft.examples,
                  { problem: "", steps: [""], result: "" },
                ],
              })
            }
          >
            Add worked example
          </button>
        </section>
        <details className="outline-details">
          <summary>Facts, scope &amp; research sources</summary>
          {listFields.slice(1).map(([key, label]) => (
            <section key={key}>
              <p className="eyebrow">{label}</p>
              <ListField
                label={label}
                values={draft[key]}
                onChange={(values) => setDraft({ ...draft, [key]: values })}
              />
            </section>
          ))}
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
        <p className="muted small">
          Teaching time: {total}s / {minutes * 60}s
        </p>
        {validation && <p role="alert">{validation}</p>}
        <ErrorNotice error={error} />
        <div className="outline-edit-actions">
          <Button type="submit">
            {pending ? "Saving outline…" : "Save outline"}
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel edits
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
