"""Select and run the backend that turns prompts into a commit message."""

from typing import Any


def normalize_legacy_config(config: Any) -> Any:
    """Move a legacy top-level ``openai`` block under ``api``; ``api`` keys win."""
    if not isinstance(config, dict) or "openai" not in config:
        return config
    normalized = dict(config)
    legacy = normalized.pop("openai")
    if not isinstance(legacy, dict):
        return normalized
    api = normalized.get("api")
    normalized["api"] = {
        "provider": "openai",
        **legacy,
        **(api if isinstance(api, dict) else {}),
    }
    return normalized
