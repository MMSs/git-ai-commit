"""Normalize commit-generation parameters for supported OpenAI models."""

import re
from dataclasses import dataclass
from typing import Any

EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class ModelCapabilities:
    efforts: tuple[str, ...]
    temperature_without_reasoning: bool = True


ORIGINAL_GPT5 = ModelCapabilities(("minimal", "low", "medium", "high"), False)
GPT51 = ModelCapabilities(("none", "low", "medium", "high"))
GPT52_TO_55 = ModelCapabilities(("none", "low", "medium", "high", "xhigh"))
GPT56_AND_6 = ModelCapabilities(("none", "low", "medium", "high", "xhigh", "max"))
GPT6_REASONING_ONLY = ModelCapabilities(("low", "medium", "high", "xhigh", "max"))
O_SERIES = ModelCapabilities(("low", "medium", "high"), False)

# Verified against official model pages and migration guidance, 2026-10-14.
# Unknown variants keep API defaults instead of inheriting family-level settings.
MODEL_CAPABILITIES = {
    "gpt-5": ORIGINAL_GPT5,
    "gpt-5-mini": ORIGINAL_GPT5,
    "gpt-5-nano": ORIGINAL_GPT5,
    "gpt-5.1": GPT51,
    "gpt-5.2": GPT52_TO_55,
    "gpt-5.4": GPT52_TO_55,
    "gpt-5.4-mini": GPT52_TO_55,
    "gpt-5.4-nano": GPT52_TO_55,
    "gpt-5.5": GPT52_TO_55,
    "gpt-5.6": GPT56_AND_6,
    "gpt-5.6-sol": GPT56_AND_6,
    "gpt-5.6-terra": GPT56_AND_6,
    "gpt-5.6-luna": GPT56_AND_6,
    "gpt-6-luna": GPT56_AND_6,
    "gpt-6-sol": GPT56_AND_6,
    "gpt-6.1-sol": GPT6_REASONING_ONLY,
    "gpt-6-astra": GPT6_REASONING_ONLY,
}


def normalize_effort(
    effort: str | bool | None, capabilities: ModelCapabilities
) -> str | None:
    """Preserve supported effort, otherwise choose a compatible boundary."""
    if (
        effort is None
        or effort is False
        or (isinstance(effort, str) and not effort.strip())
    ):
        return None
    if not isinstance(effort, str) or effort.strip().lower() not in EFFORT_ORDER:
        raise ValueError(f"Invalid reasoning_effort: {effort!r}. Use {EFFORT_ORDER}.")
    effort = effort.strip().lower()
    if effort in capabilities.efforts:
        return effort
    if effort == "minimal":
        return "low"
    if effort == "none":
        return capabilities.efforts[0]
    return capabilities.efforts[-1]


def model_parameters(config: dict[str, Any]) -> dict[str, Any]:
    """Build Chat Completions options without unsupported effort or sampling."""
    model = config["model"]
    alias = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
    capabilities = MODEL_CAPABILITIES.get(alias)
    if alias in {"o1", "o3", "o3-mini", "o4-mini"}:
        capabilities = O_SERIES

    params: dict[str, Any] = {"model": model}
    if capabilities is not None:
        effort = normalize_effort(config.get("reasoning_effort"), capabilities)
        if effort is not None:
            params["reasoning_effort"] = effort
        use_temperature = (
            capabilities.temperature_without_reasoning and effort == "none"
        )
    else:
        # Only established non-reasoning families receive sampling parameters.
        # Future GPT/o-series models and chat aliases retain conservative defaults.
        use_temperature = bool(
            re.match(r"^gpt-(?:4(?:[.-]|$)|3\.5(?:-|$))", alias)
            or alias == "chatgpt-4o-latest"
        )
    if use_temperature:
        params["temperature"] = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens") or 0
    if max_tokens > 0:
        params["max_completion_tokens"] = max_tokens
    return params
