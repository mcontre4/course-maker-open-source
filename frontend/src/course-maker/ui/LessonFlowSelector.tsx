import { useId } from "react";
import type { LessonFlow } from "../application/lesson-flow";
import "./styles/generation-mode.css";

const flows = [
  {
    value: "automatic",
    name: "Automatic",
    tag: "Hands-off",
    description:
      "We build the outline, script and video in one go. Edit it afterwards if you like.",
  },
  {
    value: "guided",
    name: "Guided",
    tag: "You review each step",
    description:
      "Check the outline, and optionally the script, before any video is made.",
  },
] as const;

export function LessonFlowSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: LessonFlow;
  onChange: (flow: LessonFlow) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <fieldset className="generation-mode lesson-flow" disabled={disabled}>
      <legend className="sr-only">How should we make it?</legend>
      <div className="generation-mode-options flow-options">
        {flows.map((flow) => (
          <label className="generation-mode-option" key={flow.value}>
            <input
              type="radio"
              name={id}
              value={flow.value}
              checked={value === flow.value}
              onChange={() => onChange(flow.value)}
              aria-label={flow.name}
            />
            <span className="generation-mode-surface">
              <span className="generation-mode-heading">
                <strong>{flow.name}</strong>
                <span className="generation-mode-check" aria-hidden="true">
                  ✓
                </span>
              </span>
              <span className="generation-mode-tag">{flow.tag}</span>
              <span className="generation-mode-description">
                {flow.description}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
