import type { StyleInput, StyleResponse } from "../application/style";

export function styleFixture(input: StyleInput, version = 1): StyleResponse {
  return {
    visualStyleId: input.visualStyleId || "flat-vector-science",
    visualStyleVersion: 1,
    reviewOutput: input.reviewOutput ?? true,
    request: input.description,
    audience: input.audience,
    requestedVoiceId: input.voiceId,
    accent: input.accent ?? "American",
    tone: input.tone ?? "",
    requestedPacing: input.pacing ?? "",
    voiceId: input.voiceId,
    summary: "Style will be planned with your outline.",
    teaching: "Concrete examples",
    writing: "Clear explanations",
    visuals: "Readable diagrams",
    motion: "Purposeful reveals",
    pacing: "Natural",
    voiceDescription: "Educational narrator",
    delivery: "",
    voiceName: "Automatic",
    resolved: false,
    version,
  };
}
