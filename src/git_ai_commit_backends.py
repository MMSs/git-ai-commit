"""Select and run the backend that turns prompts into a commit message."""

import re
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


_PREAMBLE = re.compile(r"\A\s*here(?:'s| is)\b[^\n]*:[ \t]*\n+", re.IGNORECASE)
_FENCE = re.compile(r"\A\s*```[^\n]*\n(.*?)\n?```\s*\Z", re.DOTALL)


def clean_output(text: str) -> str:
    """Strip wrappers that chat-style models add around a commit message.

    Leading spaces are kept: completion mode continues the user's text.
    """
    text = _PREAMBLE.sub("", text, count=1)
    fence = _FENCE.match(text)
    if fence:
        text = fence.group(1)
    text = text.rstrip()
    body = text.lstrip()
    if len(body) >= 2 and body[0] == body[-1] == '"' and body.count('"') == 2:
        text = body[1:-1]
    return text
