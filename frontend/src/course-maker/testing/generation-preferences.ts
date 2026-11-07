import type {
  GenerationMode,
  GenerationPreferences,
} from "../application/generation-mode";

export class MemoryGenerationPreferences implements GenerationPreferences {
  readonly values = new Map<string, GenerationMode>();
  get(scope: string) {
    return this.values.get(scope);
  }
  save(scope: string, mode: GenerationMode) {
    this.values.set(scope, mode);
  }
}
