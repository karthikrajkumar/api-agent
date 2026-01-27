"""Utilities for safe ContextVar access."""

from contextvars import ContextVar
from typing import TypeVar

T = TypeVar("T")


def safe_get_contextvar(var: ContextVar[T], default: T) -> T:
    """Safe ContextVar access with default.

    Returns value if set, otherwise returns default without setting.
    """
    try:
        return var.get()
    except LookupError:
        return default


def safe_append_contextvar_list(var: ContextVar[list[T]], item: T) -> None:
    """Append to ContextVar list if initialized.

    Silently ignores if ContextVar not set (expected in some contexts).
    """
    try:
        var.get().append(item)
    except LookupError:
        pass  # Expected - list not initialized for this context
