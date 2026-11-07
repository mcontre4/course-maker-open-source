import type {
  GenerationMode,
  GenerationPreferences,
} from "../../application/generation-mode";
import type { KeyValueStorage } from "./browser-course-repository";

export class BrowserGenerationPreferences implements GenerationPreferences {
  constructor(private readonly storage: KeyValueStorage) {}
  get(scope: string): GenerationMode | undefined {
    try {
      const value = this.storage.getItem("course-maker:generation:v1:" + scope);
      if (value === "fast" || value === "balanced" || value === "pro")
        return value;
    } catch {
      /* Preferences are optional when site storage is unavailable. */
    }
    return undefined;
  }
  save(scope: string, mode: GenerationMode) {
    try {
      this.storage.setItem("course-maker:generation:v1:" + scope, mode);
    } catch {
      /* Generation remains usable without persistent preferences. */
    }
  }
}
