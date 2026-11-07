import { useId } from "react";
import {
  animatorModels,
  defaultAnimatorModels,
  type AnimatorModelChoice,
} from "../application/animator-model";
import type { GenerationMode } from "../application/generation-mode";
import "./styles/animator-model.css";

export function AnimatorModelSelector({
  value,
  onChange,
  mode,
  disabled = false,
  scope = "animation",
}: {
  value: AnimatorModelChoice;
  onChange(value: AnimatorModelChoice): void;
  mode: GenerationMode;
  disabled?: boolean;
  scope?: "animation" | "generation";
}) {
  const id = useId();
  const effective = value || defaultAnimatorModels[mode];
  const selected = animatorModels.find((model) => model.id === effective)!;
  const automatic = animatorModels.find(
    (model) => model.id === defaultAnimatorModels[mode],
  )!;
  return (
    <div className="animator-model">
      <label htmlFor={id}>
        {scope === "generation" ? "Generation model" : "Animator model"}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        aria-describedby={`${id}-price ${id}-scope`}
        onChange={(event) =>
          onChange(event.target.value as AnimatorModelChoice)
        }
      >
        <option value="">
          Automatic — {automatic.name} ({mode})
        </option>
        {animatorModels.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name} · {model.tier} · ${model.input} in / ${model.output}{" "}
            out
          </option>
        ))}
      </select>
      <p id={`${id}-price`} className="muted small">
        {selected.name}: ${selected.input} input / ${selected.output} output per
        1M tokens (USD). Standard rates checked Oct 30, 2026; actual cost varies
        with token usage, reasoning, caching, context length, and retries.
        {"priceNote" in selected ? ` ${selected.priceNote}` : ""}
      </p>
      <p id={`${id}-scope`} className="muted small">
        {scope === "generation"
          ? "Applies to outlines, lesson content, storyboards, style planning, and guide chats throughout this browser. Animation and AI review use the Animator model. Automatic follows generation mode."
          : "Applies to animation and AI review for both engines. Automatic follows your generation mode. Narration and rendering are billed separately."}
      </p>
    </div>
  );
}
