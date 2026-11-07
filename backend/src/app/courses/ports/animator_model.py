"""Supported, explicit model choices for illustration and animation authoring."""

from enum import StrEnum


class AnimatorModel(StrEnum):
    LUNA = "openai/gpt-6-luna"
    LUNA_FAST = "openai/gpt-6-luna:fast"
    TERRA = "openai/gpt-6.1-terra"
    TERRA_FAST = "openai/gpt-6.1-terra:fast"
    SOL = "openai/gpt-6.1-sol"
    SOL_FAST = "openai/gpt-6.1-sol:fast"
    SONNET = "anthropic/claude-sonnet-5.5"
    OPUS = "anthropic/claude-opus-5.5"
    OPUS_FAST = "anthropic/claude-opus-5.5:fast"
    HAIKU = "anthropic/claude-haiku-5.5"
