import { useContext, useState } from "react";
import type {
  GenerationMode,
  GenerationPreferences,
} from "../application/generation-mode";
import { ApplicationContext } from "./application-context";

export function useGenerationMode(
  scope: string,
  parent?: string,
  initial?: GenerationMode,
  injectedPreferences?: GenerationPreferences,
  defaultMode: GenerationMode = "balanced",
) {
  const app = useContext(ApplicationContext);
  const preferences = injectedPreferences ?? app?.generationPreferences;
  const [mode, setMode] = useState<GenerationMode>(
    () =>
      initial ??
      preferences?.get(scope) ??
      (parent ? preferences?.get(parent) : undefined) ??
      defaultMode,
  );
  function remember(scope: string, mode: GenerationMode) {
    preferences?.save(scope, mode);
  }
  function changeMode(next: GenerationMode) {
    setMode(next);
    remember(scope, next);
  }
  return [mode, changeMode, remember] as const;
}
