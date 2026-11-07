import type { CourseResponse } from "./dto";
import type { GenerationMode } from "./generation-mode";
import type { StandaloneLessonResponse } from "./standalone-lessons";

export type StyleInput = Readonly<{
  visualStyleId?: string;
  reviewOutput?: boolean;
  description: string;
  audience: string;
  voiceId: string;
  accent?: string;
  tone?: string;
  pacing?: string;
}>;
export type StyleResponse = Readonly<{
  visualStyleId?: string;
  visualStyleVersion?: number;
  reviewOutput?: boolean;
  request: string;
  audience: string;
  summary: string;
  teaching: string;
  writing: string;
  visuals: string;
  motion: string;
  pacing: string;
  voiceDescription: string;
  delivery: string;
  voiceId: string;
  voiceName: string;
  version: number;
  requestedVoiceId?: string;
  voiceNotice?: string;
  resolved?: boolean;
  accent?: string;
  tone?: string;
  requestedPacing?: string;
}>;
export type VoiceResponse = Readonly<{
  id: string;
  name: string;
  description: string;
  previewUrl: string | null;
  labels: readonly string[];
}>;
export type UpdateStyleRequest = Readonly<{
  id: string;
  kind: "course" | "lesson";
  lessonId?: string;
  style: StyleInput | null;
  expectedVersion: number;
  generationMode?: GenerationMode;
}>;
export interface StyleBackend {
  voices(): Promise<readonly VoiceResponse[]>;
  update(
    request: UpdateStyleRequest,
  ): Promise<CourseResponse | StandaloneLessonResponse>;
}
export class ListVoices {
  constructor(private readonly backend: StyleBackend) {}
  execute() {
    return this.backend.voices();
  }
}
export class UpdateStyle {
  constructor(private readonly backend: StyleBackend) {}
  execute(request: UpdateStyleRequest) {
    if (
      request.style &&
      (request.style.description.length > 2000 ||
        request.style.audience.length > 2000)
    )
      throw new Error("Style and audience must be at most 2,000 characters.");
    return this.backend.update(request);
  }
}
export interface StyleApplication {
  voices: Pick<ListVoices, "execute">;
  update: Pick<UpdateStyle, "execute">;
}

export function styleInputFromResponse(
  style?: StyleResponse | null,
): StyleInput {
  return {
    visualStyleId: style ? (style.visualStyleId ?? "flat-vector-science") : "",
    reviewOutput: style?.reviewOutput ?? true,
    description: style?.request ?? "",
    audience: style?.audience ?? "",
    voiceId: style?.requestedVoiceId ?? style?.voiceId ?? "",
    accent: style?.accent ?? "American",
    tone: style?.tone ?? "",
    pacing: style?.requestedPacing ?? "",
  };
}
