import {
  animatorModels,
  type AnimatorModelChoice,
} from "../../application/animator-model";
import type { ModelPreferences } from "../../application/model-preferences";
import type { KeyValueStorage } from "./browser-course-repository";

const key = "course-maker:generation-model";

export class BrowserModelPreferences implements ModelPreferences {
  private listeners = new Set<() => void>();
  private model: AnimatorModelChoice = "";

  constructor(private readonly storage: KeyValueStorage) {
    try {
      const saved = storage.getItem(key);
      this.model = animatorModels.find((model) => model.id === saved)?.id ?? "";
    } catch {
      /* Keep automatic mode when browser storage is unavailable. */
    }
  }
  get = () => this.model;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  save(model: AnimatorModelChoice) {
    this.model = model;
    try {
      this.storage.setItem(key, model);
    } catch {
      /* Keep this session's choice. */
    }
    this.listeners.forEach((listener) => listener());
  }
}
