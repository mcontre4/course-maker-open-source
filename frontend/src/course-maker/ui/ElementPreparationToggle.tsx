import { useId } from "react";

export function ElementPreparationToggle({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange(value: boolean): void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          disabled={disabled}
          aria-describedby={id}
        />{" "}
        Pre-generate visual elements
      </label>
      <p id={id} className="muted small">
        Experimental. Identify whole objects in the storyboard and build them in
        parallel before animation. The animator can adapt the artwork. Applies
        to the next run; adds model calls.
      </p>
    </div>
  );
}
