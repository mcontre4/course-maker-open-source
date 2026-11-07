import { useContext, useState, useSyncExternalStore } from "react";
import type { AnimatorModelChoice } from "../application/animator-model";
import type { GenerationMode } from "../application/generation-mode";
import { ApplicationContext } from "./application-context";
import { AnimatorModelSelector } from "./AnimatorModelSelector";

const subscribe = () => () => {};
const automatic = () => "" as const;

export function GenerationModelSelector({
  mode,
  disabled,
}: {
  mode: GenerationMode;
  disabled: boolean;
}) {
  const preferences = useContext(ApplicationContext)?.modelPreferences;
  const saved = useSyncExternalStore(
    preferences?.subscribe ?? subscribe,
    preferences?.get ?? automatic,
  );
  const [local, setLocal] = useState<AnimatorModelChoice>("");
  return (
    <AnimatorModelSelector
      mode={mode}
      disabled={disabled}
      scope="generation"
      value={preferences ? saved : local}
      onChange={(model) => {
        if (preferences) preferences.save(model);
        else setLocal(model);
      }}
    />
  );
}
