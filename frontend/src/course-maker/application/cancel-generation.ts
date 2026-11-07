export type CancelGenerationRequest = Readonly<{
  kind: "course" | "lesson";
  id: string;
}>;

export interface GenerationCancellation {
  cancel(request: CancelGenerationRequest): Promise<boolean>;
}

export class CancelGeneration {
  constructor(private readonly backend: GenerationCancellation) {}
  execute(request: CancelGenerationRequest) {
    return this.backend.cancel(request);
  }
}
