"""Task store for shared team task management.

This module is a thin backward-compatibility shim. ``TaskStore``,
``TaskLockError`` and ``BaseTaskStore`` are exposed lazily via
``__getattr__`` and resolve to the canonical implementations under
:mod:`clawteam.store`.

New code should import directly from :mod:`clawteam.store`.
"""

from __future__ import annotations

from typing import Any

from clawteam.store.base import TaskLockError  # noqa: F401  (re-exported)

__all__ = ["TaskStore", "TaskLockError", "BaseTaskStore"]  # noqa: F822  (resolved via __getattr__)


def __getattr__(name: str) -> Any:
    if name == "TaskStore":
        from clawteam.store.file import FileTaskStore
        return FileTaskStore
    if name == "TaskLockError":
        from clawteam.store.base import TaskLockError
        return TaskLockError
    if name == "BaseTaskStore":
        from clawteam.store.base import BaseTaskStore
        return BaseTaskStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
