import type { AnimatorModelChoice } from "./animator-model";

export interface ModelPreferences {
  get(): AnimatorModelChoice;
  save(model: AnimatorModelChoice): void;
  subscribe(listener: () => void): () => void;
}
