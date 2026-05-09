"""Symlink ``<repo>/.github/skills/<name>`` into ``~/.claude/skills/`` so
ClawTeam's ``--skill`` machinery (which reads from ``~/.claude/skills``) can
discover repository-local skills without copying.

Idempotent: existing real directories or differing symlinks are left alone.
"""

from __future__ import annotations

import os
from pathlib import Path


def ensure_skills_symlinked(
    repo_root: str | os.PathLike[str] | None,
    target_root: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """Symlink each ``<repo_root>/.github/skills/<name>`` into ``~/.claude/skills/``.

    Returns a dict mapping ``status -> [skill_name, ...]`` where ``status`` is
    one of ``linked``, ``existing``, ``skipped``, or ``missing``. Errors are
    swallowed and reported as ``skipped`` so a misconfigured environment never
    blocks an agent spawn.
    """
    result: dict[str, list[str]] = {
        "linked": [],
        "existing": [],
        "skipped": [],
        "missing": [],
    }
    if not repo_root:
        return {k: ",".join(v) for k, v in result.items()}

    src_root = Path(repo_root) / ".github" / "skills"
    if not src_root.is_dir():
        result["missing"].append(str(src_root))
        return {k: ",".join(v) for k, v in result.items()}

    dst_root = Path(target_root) if target_root else Path.home() / ".claude" / "skills"
    try:
        dst_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        result["skipped"].append(str(dst_root))
        return {k: ",".join(v) for k, v in result.items()}

    for skill_dir in sorted(src_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name
        link = dst_root / name
        try:
            if link.is_symlink():
                # Leave alone — user or earlier spawn may have configured it.
                result["existing"].append(name)
                continue
            if link.exists():
                result["existing"].append(name)
                continue
            link.symlink_to(skill_dir, target_is_directory=True)
            result["linked"].append(name)
        except OSError:
            result["skipped"].append(name)

    return {k: ",".join(v) for k, v in result.items()}


__all__ = ["ensure_skills_symlinked"]
