import type { GenerationMode } from "./generation-mode";

// USD per million tokens, verified 2026-10-30; Opus Fast 2026-10-31. See docs/animator-agent.md.
export const animatorModels = [
  {
    id: "openai/gpt-6-luna",
    name: "GPT-6 Luna",
    tier: "Budget",
    input: 0.1,
    output: 0.5,
  },
  {
    id: "openai/gpt-6-luna:fast",
    name: "GPT-6 Luna Fast",
    tier: "Budget · Fast",
    input: 0.2,
    output: 1,
  },
  {
    id: "openai/gpt-6.1-terra",
    name: "GPT-6.1 Terra",
    tier: "Balanced",
    input: 1,
    output: 5,
  },
  {
    id: "openai/gpt-6.1-terra:fast",
    name: "GPT-6.1 Terra Fast",
    tier: "Balanced · Fast",
    input: 2,
    output: 10,
  },
  {
    id: "openai/gpt-6.1-sol",
    name: "GPT-6.1 Sol",
    tier: "Quality",
    input: 2,
    output: 10,
  },
  {
    id: "openai/gpt-6.1-sol:fast",
    name: "GPT-6.1 Sol Fast",
    tier: "Quality · Fast",
    input: 4,
    output: 20,
  },
  {
    id: "anthropic/claude-sonnet-5.5",
    name: "Claude Sonnet 5.5",
    tier: "Quality",
    input: 2,
    output: 10,
  },
  {
    id: "anthropic/claude-opus-5.5",
    name: "Claude Opus 5.5",
    tier: "Premium",
    input: 4,
    output: 20,
  },
  {
    id: "anthropic/claude-opus-5.5:fast",
    name: "Claude Opus 5.5 Fast",
    tier: "Premium · Fast",
    input: 8,
    output: 40,
  },
  {
    id: "anthropic/claude-haiku-5.5",
    name: "Claude Haiku 5.5",
    tier: "Budget",
    input: 0.1,
    output: 0.5,
    priceNote:
      "For prompts over 100K tokens: $0.50 input / $2.50 output per 1M tokens.",
  },
] as const;

export type AnimatorModel = (typeof animatorModels)[number]["id"];
export type AnimatorModelChoice = AnimatorModel | "";

export const defaultAnimatorModels: Record<GenerationMode, AnimatorModel> = {
  fast: "anthropic/claude-sonnet-5.5",
  balanced: "anthropic/claude-opus-5.5",
  pro: "anthropic/claude-opus-5.5",
};
