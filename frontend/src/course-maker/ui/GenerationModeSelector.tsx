import { useId, type ReactNode } from "react";
import { GenerationModelSelector } from "./GenerationModelSelector";
import type { GenerationMode } from "../application/generation-mode";
import "./styles/generation-mode.css";

const modes = [
  {
    value: "fast",
    name: "Fast",
    tag: "Lowest cost",
    description: "Quick drafts for everyday topics.",
    detail: "Prioritizes speed and affordability.",
  },
  {
    value: "balanced",
    name: "Balanced",
    tag: "Recommended",
    description: "Quality and speed in balance.",
    detail: "A thoughtful starting point for most lessons.",
  },
  {
    value: "pro",
    name: "Pro",
    tag: "Quality first",
    description: "More reasoning for complex topics.",
    detail: "Prioritizes quality; takes longer and costs more.",
  },
] as const;

export function GenerationModeSelector({
  value,
  onChange,
  disabled = false,
  showLegend = true,
  children,
}: {
  value: GenerationMode;
  onChange: (mode: GenerationMode) => void;
  disabled?: boolean;
  /** Hide the legend when a surrounding heading already names the choice. */
  showLegend?: boolean;
  /** Extra expert controls shown with the model choice. */
  children?: ReactNode;
}) {
  const id = useId();
  return (
    <fieldset
      className="generation-mode"
      disabled={disabled}
      aria-describedby={id + "-detail"}
    >
      <legend className={showLegend ? undefined : "sr-only"}>
        Quality &amp; speed
      </legend>
      <div className="generation-mode-options">
        {modes.map((mode) => (
          <label className="generation-mode-option" key={mode.value}>
            <input
              type="radio"
              name={id}
              value={mode.value}
              checked={value === mode.value}
              onChange={() => onChange(mode.value)}
              aria-label={mode.name}
            />
            <span className="generation-mode-surface">
              <span className="generation-mode-heading">
                <strong>{mode.name}</strong>
                <span className="generation-mode-check" aria-hidden="true">
                  ✓
                </span>
              </span>
              <span className="generation-mode-tag">{mode.tag}</span>
              <span className="generation-mode-description">
                {mode.description}
              </span>
            </span>
          </label>
        ))}
      </div>
      <p
        className="generation-mode-detail"
        id={id + "-detail"}
        aria-live="polite"
      >
        {modes.find((mode) => mode.value === value)?.detail} Applies to the next
        generation.
      </p>
      <details className="generation-technical">
        <summary>Technical settings</summary>
        <GenerationModelSelector mode={value} disabled={disabled} />
        {children}
      </details>
    </fieldset>
  );
}

/** The mode picker as a collapsed settings row that shows the current choice. */
export function QualitySettings(
  props: Parameters<typeof GenerationModeSelector>[0],
) {
  const mode = modes.find((item) => item.value === props.value);
  return (
    <details className="settings-disclosure quality-settings">
      <summary>
        Quality &amp; speed
        <span className="summary-value">
          {mode?.name}
          {mode?.value === "balanced" ? " (recommended)" : ""}
        </span>
      </summary>
      <GenerationModeSelector {...props} />
    </details>
  );
}
