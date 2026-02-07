"""Recipe tool naming helpers."""

import re


def sanitize_tool_name(name: str | None) -> str:
    """Normalize tool name to a safe slug."""
    slug = re.sub(r"[^\w\s]", "", (name or "").lower())
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return slug or "recipe"
