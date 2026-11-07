"""Translate application model choices into OpenRouter request fields."""


def model_options(model: str) -> dict[str, str]:
    options = {"model": model.removesuffix(":fast")}
    if model.endswith(":fast"):
        options["service_tier"] = "fast" if model.startswith("anthropic/") else "priority"
    return options
